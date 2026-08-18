import base64
import binascii
import json
import mimetypes
import uuid
from urllib.parse import quote
from datetime import datetime, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, Response
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from sqlalchemy import or_

from app.extensions import db, csrf
from app.models import Message, User, Notification, CallSignal, TypingState, Follow
from app.utils.helpers import get_status_icon, get_user_status, allowed_audio_file
from app.utils.image_storage import prepare_image_data
from app.services.anter_assistant import (
    ASSISTANT_TEXT_ONLY_REPLY,
    get_assistant_reply,
    is_anter_assistant,
)
from app.services.anter_memory import clear_memory, remember_assistant_reply, remember_user_message

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

    # يعرض الشريط الحسابات التي يتابعها المستخدم وهي متصلة الآن. النتيجة محدودة
    # لتبقى الصفحة خفيفة وسريعة على الهاتف، وتُفتح المحادثة مباشرة عند الضغط عليها.
    followed_users = (
        User.query.join(Follow, Follow.followed_id == User.id)
        .filter(Follow.follower_id == current_user.id)
        .order_by(User.last_seen.desc())
        .limit(30)
        .all()
    )
    online_friends = [user for user in followed_users if get_user_status(user)['status'] == 'online']

    return render_template(
        'messages/inbox.html',
        conversations=conversations,
        online_friends=online_friends,
        get_status_icon=get_status_icon,
        get_user_status=get_user_status,
    )


@messages_bp.route('/<int:user_id>')
@login_required
def chat(user_id):
    other = User.query.get_or_404(user_id)
    messages = Message.query.filter(
        or_(
            (Message.sender_id == current_user.id) & (Message.receiver_id == other.id) & (Message.deleted_by_sender == False),
            (Message.sender_id == other.id) & (Message.receiver_id == current_user.id) & (Message.deleted_by_receiver == False),
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
        is_anter_assistant=is_anter_assistant(other),
    )


TYPING_TTL_SECONDS = 6
CHAT_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def _can_message_user(other):
    privacy = getattr(other, 'message_privacy', 'everyone') or 'everyone'
    if privacy == 'none':
        return False
    if privacy == 'followers':
        return Follow.query.filter_by(
            follower_id=other.id,
            followed_id=current_user.id,
        ).first() is not None
    return True


def _prepare_chat_attachment(uploaded_file):
    if not uploaded_file or not uploaded_file.filename:
        return None, None, None, None

    filename = secure_filename(uploaded_file.filename)
    if not filename or '.' not in filename:
        return None, None, None, None
    extension = filename.rsplit('.', 1)[1].lower()
    max_bytes = current_app.config['MAX_CHAT_ATTACHMENT_BYTES']

    if extension in CHAT_IMAGE_EXTENSIONS:
        data, mime_type = prepare_image_data(uploaded_file)
        if not data:
            return None, None, None, None
        return data, mime_type, filename, 'image'

    if extension not in current_app.config['ALLOWED_CHAT_FILE_EXTENSIONS']:
        return None, None, None, None
    data = uploaded_file.read(max_bytes + 1)
    if not data or len(data) > max_bytes:
        return None, None, None, None
    mime_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
    return data, mime_type, filename, 'file'


@messages_bp.route('/typing/<int:user_id>', methods=['POST'])
@login_required
@csrf.exempt
def set_typing(user_id):
    """Store a short-lived typing snapshot; every request returns immediately."""
    other = User.query.get_or_404(user_id)
    if not _can_message_user(other):
        return jsonify({'success': False, 'typing': False, 'message': 'المراسلة غير متاحة لهذا المستخدم.'}), 403

    data = request.get_json(silent=True) or request.form
    value = data.get('typing', False)
    is_typing = value is True or str(value).strip().lower() in {'1', 'true', 'yes', 'on'}
    state = TypingState.query.filter_by(
        sender_id=current_user.id,
        receiver_id=other.id,
    ).first()
    if is_typing:
        if state:
            state.updated_at = datetime.utcnow()
        else:
            db.session.add(TypingState(
                sender_id=current_user.id,
                receiver_id=other.id,
                updated_at=datetime.utcnow(),
            ))
    elif state:
        db.session.delete(state)
    db.session.commit()
    return jsonify({'success': True, 'typing': is_typing})


@messages_bp.route('/typing/<int:user_id>', methods=['GET'])
@login_required
def get_typing(user_id):
    """Read a typing snapshot that is valid for only a few seconds."""
    other = User.query.get_or_404(user_id)
    cutoff = datetime.utcnow() - timedelta(seconds=TYPING_TTL_SECONDS)
    state = TypingState.query.filter(
        TypingState.sender_id == other.id,
        TypingState.receiver_id == current_user.id,
        TypingState.updated_at >= cutoff,
    ).first()
    return jsonify({'typing': state is not None, 'ttl': TYPING_TTL_SECONDS})


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
    if not _can_message_user(other):
        flash('هذا المستخدم لا يستقبل رسائل منك حاليًا.', 'warning')
        return redirect(url_for('messages.chat', user_id=user_id))
    content = request.form.get('content', '').strip()
    parent_id = request.form.get('parent_id', type=int)
    uploaded_audio = request.files.get('audio')
    uploaded_attachment = request.files.get('attachment')
    audio_data = None
    audio_mime = None
    attachment_data = None
    attachment_mime = None
    attachment_name = None
    attachment_kind = None

    if uploaded_audio and uploaded_audio.filename and uploaded_attachment and uploaded_attachment.filename:
        flash('أرسل رسالة صوتية أو مرفقًا واحدًا في كل مرة.', 'warning')
        return redirect(url_for('messages.chat', user_id=user_id))

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

    if uploaded_attachment and uploaded_attachment.filename:
        attachment_data, attachment_mime, attachment_name, attachment_kind = _prepare_chat_attachment(uploaded_attachment)
        if not attachment_data:
            flash('نوع المرفق غير مدعوم أو حجمه أكبر من 8 ميجابايت.', 'danger')
            return redirect(url_for('messages.chat', user_id=user_id))

    if content or audio_data or attachment_data:
        try:
            typing_state = TypingState.query.filter_by(
                sender_id=current_user.id,
                receiver_id=other.id,
            ).first()
            if typing_state:
                db.session.delete(typing_state)
            message = Message(
                sender_id=current_user.id,
                receiver_id=other.id,
                content=content,
                audio_data=audio_data,
                audio_mime=audio_mime,
                attachment_data=attachment_data,
                attachment_mime=attachment_mime,
                attachment_name=attachment_name,
                attachment_kind=attachment_kind,
                parent_id=parent_id
            )
            db.session.add(message)
            # تم فصل إشعارات الرسائل عن الإشعارات العامة لتظهر في قسم المراسلة فقط
            pass
            db.session.commit()
        except Exception:
            db.session.rollback()
            current_app.logger.exception('تعذر إرسال الرسالة')
            flash('تعذر إرسال الرسالة حاليًا. حاول مجددًا.', 'danger')
        else:
            if is_anter_assistant(other):
                try:
                    if audio_data or attachment_data:
                        assistant_reply = ASSISTANT_TEXT_ONLY_REPLY
                    else:
                        # تحفظ الذاكرة محلياً داخل ANTER فقط، ثم يرسل المساعد السؤال الحالي وحده للخدمة الخارجية عند الحاجة.
                        remember_user_message(current_user, other, content)
                        assistant_reply, public_error = get_assistant_reply(
                            content,
                            user=current_user,
                            assistant=other,
                        )
                        assistant_reply = assistant_reply or public_error

                    if assistant_reply:
                        db.session.add(Message(
                            sender_id=other.id,
                            receiver_id=current_user.id,
                            content=assistant_reply,
                            parent_id=message.id,
                        ))
                        db.session.commit()
                        remember_assistant_reply(current_user, other, assistant_reply)
                except Exception:
                    # لا يؤثر فشل رد المساعد في الرسالة الأصلية التي تم حفظها بالفعل.
                    db.session.rollback()
                    current_app.logger.exception('تعذر حفظ رد مساعد أنتر')

            flash('تم إرسال الرسالة.', 'success')
    else:
        flash('الرسالة فارغة.', 'danger')
    return redirect(url_for('messages.chat', user_id=user_id))


@messages_bp.route('/assistant-memory/<int:user_id>/clear', methods=['POST'])
@login_required
@csrf.exempt
def clear_assistant_memory(user_id):
    """محو ذاكرة مساعد أنتر للمستخدم الحالي من دون حذف سجل الدردشة."""
    other = User.query.get_or_404(user_id)
    if not is_anter_assistant(other):
        return jsonify({'success': False, 'message': 'هذه الميزة متاحة داخل محادثة مساعد أنتر فقط.'}), 404

    try:
        clear_memory(current_user, other)
    except Exception:
        db.session.rollback()
        current_app.logger.exception('تعذر مسح ذاكرة مساعد أنتر')
        return jsonify({'success': False, 'message': 'تعذر مسح الذاكرة حالياً. حاول مجدداً.'}), 500

    return jsonify({'success': True, 'message': 'تم مسح ذاكرة مساعد أنتر الخاصة بك. بقي سجل الرسائل كما هو.'})


@messages_bp.route('/delete/<int:message_id>', methods=['POST'])
@login_required
@csrf.exempt
def delete_message(message_id):
    message = Message.query.get_or_404(message_id)
    if current_user.id not in {message.sender_id, message.receiver_id}:
        return jsonify({'success': False, 'message': 'غير مصرح لك'}), 403
    
    delete_type = request.form.get('type', 'me') # 'me' or 'everyone'
    
    if delete_type == 'everyone':
        if message.sender_id != current_user.id:
            return jsonify({'success': False, 'message': 'لا يمكنك حذف رسالة لست مرسلها عند الجميع'}), 403
        message.is_deleted_everyone = True
    else:
        if message.sender_id == current_user.id:
            message.deleted_by_sender = True
        else:
            message.deleted_by_receiver = True
            
    db.session.commit()
    return jsonify({'success': True})


@messages_bp.route('/forward/<int:message_id>', methods=['POST'])
@login_required
@csrf.exempt
def forward_message(message_id):
    original = Message.query.get_or_404(message_id)
    target_user_id = request.form.get('target_user_id', type=int)
    if not target_user_id:
        return jsonify({'success': False, 'message': 'يجب تحديد مستلم'}), 400
    
    target_user = User.query.get_or_404(target_user_id)
    if not _can_message_user(target_user):
        return jsonify({'success': False, 'message': 'لا يمكن مراسلة هذا المستخدم'}), 403
        
    forwarded = Message(
        sender_id=current_user.id,
        receiver_id=target_user_id,
        content=original.content,
        audio_data=original.audio_data,
        audio_mime=original.audio_mime,
        attachment_data=original.attachment_data,
        attachment_mime=original.attachment_mime,
        attachment_name=original.attachment_name,
        attachment_kind=original.attachment_kind,
        # يمكن إضافة علامة "رسالة محولة" في المحتوى مستقبلاً
    )
    db.session.add(forwarded)
    db.session.commit()
    return jsonify({'success': True, 'redirect': url_for('messages.chat', user_id=target_user_id)})


@messages_bp.route('/send-audio/<int:user_id>', methods=['POST'])
@login_required
@csrf.exempt
def send_audio_message(user_id):
    """استقبال الصوت كـ base64 لتجاوز فشل multipart في بعض بيئات الإنتاج."""
    other = User.query.get_or_404(user_id)
    if not _can_message_user(other):
        return jsonify({'success': False, 'message': 'هذا المستخدم لا يستقبل رسائل منك حاليًا.'}), 403
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
        typing_state = TypingState.query.filter_by(
            sender_id=current_user.id,
            receiver_id=other.id,
        ).first()
        if typing_state:
            db.session.delete(typing_state)
        message = Message(
            sender_id=current_user.id,
            receiver_id=other.id,
            content=content,
            audio_data=audio_data,
            audio_mime=audio_mime,
        )
        db.session.add(message)
        # تم فصل إشعارات الرسائل الصوتية عن الإشعارات العامة
        pass
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
    audio_mime = message.audio_mime or 'application/octet-stream'
    return Response(
        message.audio_data,
        status=200,
        mimetype=audio_mime,
        headers={
            'Content-Length': str(len(message.audio_data)),
            'Content-Disposition': f'inline; filename="voice-message-{message.id}"',
            'Cache-Control': 'private, max-age=300',
            'Accept-Ranges': 'bytes',
        },
    )


@messages_bp.route('/attachment/<int:message_id>')
@login_required
def attachment(message_id):
    """Serve a chat attachment only to the two participants in the message."""
    message = Message.query.get_or_404(message_id)
    if current_user.id not in {message.sender_id, message.receiver_id}:
        return jsonify({'message': 'غير مصرح لك بالوصول إلى هذا المرفق.'}), 403
    if not message.attachment_data:
        return jsonify({'message': 'لا يحتوي هذا السجل على مرفق.'}), 404
    disposition = 'inline' if message.attachment_kind == 'image' else 'attachment'
    filename = secure_filename(message.attachment_name or f'attachment-{message.id}')
    return Response(
        message.attachment_data,
        status=200,
        mimetype=message.attachment_mime or 'application/octet-stream',
        headers={
            'Content-Length': str(len(message.attachment_data)),
            'Content-Disposition': f"{disposition}; filename*=UTF-8''{quote(filename)}",
            'Cache-Control': 'private, max-age=300',
            'Accept-Ranges': 'bytes',
        },
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
        # تم فصل إشعارات المكالمات عن الإشعارات العامة
        pass
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


@messages_bp.route('/unread_count')
@login_required
def unread_messages_count():
    """إرجاع عدد الرسائل غير المقروءة لتحديث بادج المراسلة في الوقت الفعلي."""
    count = Message.query.filter_by(receiver_id=current_user.id, is_read=False, deleted_by_receiver=False).count()
    return jsonify({'count': count})
