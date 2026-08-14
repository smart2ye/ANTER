import base64
import binascii
import json
import uuid
from datetime import datetime, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, send_file
from io import BytesIO
from flask_login import login_required, current_user
from sqlalchemy import or_

from app.extensions import db, csrf
from app.models import Message, User, Notification, CallSignal
from app.utils.helpers import get_status_icon, allowed_audio_file

messages_bp = Blueprint('messages', __name__, url_prefix='/messages')
CALL_SIGNAL_TYPES = {'invite', 'answer', 'candidate', 'decline', 'hangup'}


def get_rtc_config():
    """تجهيز إعدادات ICE للمتصفح من متغيرات البيئة."""
    ice_servers = [{'urls': current_app.config['WEBRTC_STUN_URL']}]
    turn_url = current_app.config.get('WEBRTC_TURN_URL')
    if turn_url:
        turn_server = {'urls': turn_url}
        username = current_app.config.get('WEBRTC_TURN_USERNAME')
        credential = current_app.config.get('WEBRTC_TURN_CREDENTIAL')
        if username:
            turn_server['username'] = username
        if credential:
            turn_server['credential'] = credential
        ice_servers.append(turn_server)
    return {'iceServers': ice_servers}


@messages_bp.route('/')
@login_required
def inbox():
    # جلب الرسائل المرتبطة بالمستخدم دفعة واحدة ثم استخراج أحدث رسالة لكل محادثة.
    messages = Message.query.filter(
        or_(
            Message.sender_id == current_user.id,
            Message.receiver_id == current_user.id,
        )
    ).order_by(Message.created_at.desc()).all()

    latest_by_user = {}
    for message in messages:
        other_id = message.receiver_id if message.sender_id == current_user.id else message.sender_id
        latest_by_user.setdefault(other_id, message)

    users = User.query.filter(User.id.in_(latest_by_user.keys())).all()
    users_by_id = {user.id: user for user in users}
    conversations = [
        (users_by_id[user_id], latest_by_user[user_id])
        for user_id in latest_by_user
        if user_id in users_by_id
    ]
    conversations.sort(key=lambda item: item[1].created_at, reverse=True)

    return render_template(
        'messages/inbox.html',
        conversations=conversations,
        get_status_icon=get_status_icon,
    )


@messages_bp.route('/<int:user_id>')
@login_required
def chat(user_id):
    other = User.query.get_or_404(user_id)
    messages = Message.query.filter(
        or_(
            (Message.sender_id == current_user.id) & (Message.receiver_id == other.id),
            (Message.sender_id == other.id) & (Message.receiver_id == current_user.id),
        )
    ).order_by(Message.created_at.asc()).all()

    unread_changed = False
    for message in messages:
        if message.receiver_id == current_user.id and not message.is_read:
            message.is_read = True
            unread_changed = True
    if unread_changed:
        db.session.commit()

    return render_template(
        'messages/chat.html',
        other=other,
        messages=messages,
        get_status_icon=get_status_icon,
        rtc_config=get_rtc_config(),
    )


AUDIO_MIME_BY_EXTENSION = {
    'webm': 'audio/webm',
    'ogg': 'audio/ogg',
    'mp3': 'audio/mpeg',
    'wav': 'audio/wav',
    'm4a': 'audio/mp4',
    'aac': 'audio/aac',
}


@messages_bp.route('/send/<int:user_id>', methods=['POST'])
@login_required
@csrf.exempt
def send(user_id):
    other = User.query.get_or_404(user_id)
    content = request.form.get('content', '').strip()
    uploaded_audio = request.files.get('audio')
    audio_data = None
    audio_mime = None

    if uploaded_audio and uploaded_audio.filename:
        if not allowed_audio_file(uploaded_audio.filename):
            flash('صيغة الرسالة الصوتية غير مدعومة.', 'danger')
            return redirect(url_for('messages.chat', user_id=user_id))
        try:
            audio_data = uploaded_audio.read()
        except Exception:
            current_app.logger.exception('تعذر قراءة ملف الرسالة الصوتية')
            flash('تعذر قراءة الرسالة الصوتية حاليًا. حاول مجددًا.', 'danger')
            return redirect(url_for('messages.chat', user_id=user_id))

        max_audio_size = current_app.config['MAX_AUDIO_MESSAGE_BYTES']
        if not audio_data or len(audio_data) > max_audio_size:
            flash('يجب أن تكون الرسالة الصوتية صالحة وألا تتجاوز 10 ميجابايت.', 'danger')
            return redirect(url_for('messages.chat', user_id=user_id))

        extension = uploaded_audio.filename.rsplit('.', 1)[1].lower()
        audio_mime = AUDIO_MIME_BY_EXTENSION.get(extension, 'application/octet-stream')

    if content or audio_data:
        try:
            message = Message(
                sender_id=current_user.id,
                receiver_id=other.id,
                content=content,
                audio_data=audio_data,
                audio_mime=audio_mime,
            )
            db.session.add(message)
            notification_action = 'voice_message' if audio_data else 'message'
            db.session.add(Notification(
                user_id=other.id,
                actor_id=current_user.id,
                action=notification_action,
            ))
            db.session.commit()
        except Exception:
            db.session.rollback()
            current_app.logger.exception('تعذر إرسال الرسالة')
            flash('تعذر إرسال الرسالة حاليًا. حاول مجددًا.', 'danger')
        else:
            flash('تم إرسال الرسالة.', 'success')
    else:
        flash('الرسالة فارغة.', 'danger')
    return redirect(url_for('messages.chat', user_id=user_id))


@messages_bp.route('/send-audio/<int:user_id>', methods=['POST'])
@login_required
@csrf.exempt
def send_audio_message(user_id):
    """استقبال الصوت كـ base64 لتجاوز فشل multipart في بعض بيئات الإنتاج."""
    other = User.query.get_or_404(user_id)
    data = request.get_json(silent=True) or {}
    encoded_audio = data.get('audioData')
    filename = str(data.get('fileName', '')).strip()
    content = str(data.get('content', '')).strip()

    if not isinstance(encoded_audio, str) or not filename or not allowed_audio_file(filename):
        return jsonify({'success': False, 'message': 'ملف صوتي غير صالح.'}), 400
    if len(encoded_audio) > (current_app.config['MAX_AUDIO_MESSAGE_BYTES'] * 4 // 3) + 1024:
        return jsonify({'success': False, 'message': 'الرسالة الصوتية أكبر من الحد المسموح.'}), 413

    try:
        audio_data = base64.b64decode(encoded_audio, validate=True)
    except (binascii.Error, ValueError, TypeError):
        return jsonify({'success': False, 'message': 'تعذر قراءة بيانات الصوت.'}), 400

    max_audio_size = current_app.config['MAX_AUDIO_MESSAGE_BYTES']
    if not audio_data or len(audio_data) > max_audio_size:
        return jsonify({'success': False, 'message': 'يجب أن تكون الرسالة الصوتية صالحة وألا تتجاوز 10 ميجابايت.'}), 400

    extension = filename.rsplit('.', 1)[1].lower()
    audio_mime = AUDIO_MIME_BY_EXTENSION.get(extension, 'application/octet-stream')
    try:
        message = Message(
            sender_id=current_user.id,
            receiver_id=other.id,
            content=content,
            audio_data=audio_data,
            audio_mime=audio_mime,
        )
        db.session.add(message)
        db.session.add(Notification(
            user_id=other.id,
            actor_id=current_user.id,
            action='voice_message',
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception('تعذر إرسال الرسالة الصوتية عبر JSON')
        return jsonify({'success': False, 'message': 'تعذر إرسال الرسالة الصوتية حاليًا.'}), 500

    return jsonify({
        'success': True,
        'messageId': message.id,
        'redirect': url_for('messages.chat', user_id=user_id),
    }), 201


@messages_bp.route('/audio/<int:message_id>')
@login_required
def audio(message_id):
    """تقديم صوت الرسالة من قاعدة البيانات إلى طرف المحادثة فقط."""
    message = Message.query.get_or_404(message_id)
    if current_user.id not in {message.sender_id, message.receiver_id}:
        return jsonify({'message': 'غير مصرح لك بالوصول إلى هذا الملف.'}), 403
    if not message.audio_data:
        return jsonify({'message': 'لا يحتوي هذا السجل على رسالة صوتية.'}), 404
    return send_file(
        BytesIO(message.audio_data),
        mimetype=message.audio_mime or 'application/octet-stream',
        as_attachment=False,
        download_name=f'voice-message-{message.id}',
        conditional=True,
    )


@messages_bp.route('/calls/signal/<int:user_id>', methods=['POST'])
@login_required
@csrf.exempt
def send_call_signal(user_id):
    """إرسال إشعار WebRTC إلى طرف المحادثة عبر قاعدة البيانات."""
    receiver = User.query.get_or_404(user_id)
    if receiver.id == current_user.id:
        return jsonify({'success': False, 'message': 'لا يمكن الاتصال بالنفس.'}), 400

    data = request.get_json(silent=True) or {}
    call_id = str(data.get('callId', '')).strip()
    signal_type = str(data.get('type', '')).strip().lower()
    payload = data.get('payload', {})

    if not call_id or len(call_id) > 64 or signal_type not in CALL_SIGNAL_TYPES:
        return jsonify({'success': False, 'message': 'بيانات مكالمة غير صالحة.'}), 400

    try:
        payload_json = json.dumps(payload, ensure_ascii=False)
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': 'محتوى الإشارة غير صالح.'}), 400
    if len(payload_json) > 65535:
        return jsonify({'success': False, 'message': 'محتوى الإشارة كبير جدًا.'}), 413

    # تنظيف الإشارات القديمة لتبقى قاعدة البيانات صغيرة.
    expiry = datetime.utcnow() - timedelta(hours=1)
    CallSignal.query.filter(CallSignal.created_at < expiry).delete(synchronize_session=False)

    signal = CallSignal(
        call_id=call_id,
        signal_type=signal_type,
        payload=payload_json,
        sender_id=current_user.id,
        receiver_id=receiver.id,
    )
    db.session.add(signal)

    if signal_type == 'invite':
        db.session.add(Notification(
            user_id=receiver.id,
            actor_id=current_user.id,
            action='voice_call',
        ))
    db.session.commit()
    return jsonify({'success': True, 'signalId': signal.id})


@messages_bp.route('/calls/poll/<int:user_id>')
@login_required
def poll_call_signals(user_id):
    """إرجاع الإشارات الجديدة من طرف محادثة محدد ثم تعليمها كمستلمة."""
    User.query.get_or_404(user_id)
    signals = CallSignal.query.filter_by(
        sender_id=user_id,
        receiver_id=current_user.id,
        delivered_at=None,
    ).order_by(CallSignal.created_at.asc()).limit(50).all()

    result = []
    for signal in signals:
        try:
            payload = json.loads(signal.payload or '{}')
        except (TypeError, ValueError):
            payload = {}
        data = signal.to_dict()
        data['payload'] = payload
        result.append(data)
        signal.delivered_at = datetime.utcnow()

    if signals:
        db.session.commit()
    return jsonify({'signals': result})
