from datetime import datetime, timedelta

import json
from datetime import datetime

from flask import Blueprint, Response, current_app, g, jsonify, request
from sqlalchemy import or_
from werkzeug.utils import secure_filename

from app.extensions import csrf, db
from app.models import CallLog, CallSignal, Follow, Message, MobileAccessToken, MutedConversation, Report, TypingState, User, UserBlock
from app.services.message_safety import block_user, is_blocked_between, unblock_user
from app.services.anter_assistant import get_assistant_reply, is_anter_assistant
from app.services.anter_memory import clear_memory, remember_assistant_reply, remember_user_message
from app.utils.image_storage import prepare_image_data
from app.services.mobile_api_auth import (
    exchange_mobile_browser_authorization,
    issue_mobile_token,
    mobile_api_required,
    revoke_mobile_token,
)


mobile_api_bp = Blueprint('mobile_api', __name__, url_prefix='/api/mobile/v1')
csrf.exempt(mobile_api_bp)


def _json_error(message, status):
    return jsonify({'error': message}), status


def _user_payload(user):
    return {
        'id': user.id,
        'username': user.username,
        'name': user.name,
        'avatar': user.avatar or '',
        'isOnline': bool(user.last_seen and (datetime.utcnow() - user.last_seen).total_seconds() < 180),
        'bio': (user.bio or '').strip(),
        'lastSeen': user.last_seen.isoformat() + 'Z' if user.last_seen else None,
    }


def _mobile_device_payload(token, current_token_id):
    return {
        'id': token.id,
        'deviceName': token.device_name,
        'createdAt': token.created_at.isoformat() + 'Z',
        'lastUsedAt': token.last_used_at.isoformat() + 'Z' if token.last_used_at else None,
        'expiresAt': token.expires_at.isoformat() + 'Z',
        'isCurrent': token.id == current_token_id,
    }


def _is_mutual_follow(user, other):
    return (
        user.id != other.id
        and not is_blocked_between(user.id, other.id)
        and user.is_following(other)
        and other.is_following(user)
    )


def _is_muted(user, other):
    return MutedConversation.query.filter_by(
        user_id=user.id,
        muted_user_id=other.id,
    ).first() is not None


def _message_payload(message):
    parent = message.parent
    return {
        'id': message.id,
        'senderId': message.sender_id,
        'receiverId': message.receiver_id,
        'content': message.content or '',
        'createdAt': message.created_at.isoformat() + 'Z',
        'isRead': bool(message.is_read),
        'parentId': message.parent_id,
        'parent': {
            'id': parent.id,
            'senderId': parent.sender_id,
            'content': '' if parent.is_deleted_everyone else (parent.content or ''),
            'isDeletedEveryone': bool(parent.is_deleted_everyone),
        } if parent is not None else None,
        'attachment': {
            'name': message.attachment_name or 'مرفق',
            'mimeType': message.attachment_mime or 'application/octet-stream',
            'kind': message.attachment_kind or 'file',
            'downloadPath': f'/messages/{message.id}/attachment',
        } if message.attachment_data else None,
    }


def _prepare_mobile_attachment(uploaded_file):
    """تحقق من مرفق Mobile API قبل تخزينه في سجل الرسالة نفسه."""
    if not uploaded_file or not uploaded_file.filename:
        return None, None, None, None
    filename = secure_filename(uploaded_file.filename)
    if not filename or '.' not in filename:
        return None, None, None, None
    extension = filename.rsplit('.', 1)[1].lower()
    if extension in current_app.config['ALLOWED_EXTENSIONS']:
        data, mime_type = prepare_image_data(uploaded_file)
        return (data, mime_type, filename, 'image') if data else (None, None, None, None)
    if extension not in current_app.config['ALLOWED_CHAT_FILE_EXTENSIONS']:
        return None, None, None, None
    max_bytes = current_app.config['MAX_CHAT_ATTACHMENT_BYTES']
    data = uploaded_file.read(max_bytes + 1)
    if not data or len(data) > max_bytes:
        return None, None, None, None
    return data, uploaded_file.mimetype or 'application/octet-stream', filename, 'file'


def _update_mobile_call_log(caller, receiver, call_id, signal_type, payload):
    now = datetime.utcnow()
    if signal_type == 'invite':
        existing = CallLog.query.filter_by(call_id=call_id).first()
        if existing is None:
            requested = str((payload or {}).get('callType', 'voice')).lower()
            db.session.add(CallLog(
                call_id=call_id,
                caller_id=caller.id,
                receiver_id=receiver.id,
                call_type=requested if requested in {'voice', 'video'} else 'voice',
                status='ringing',
                started_at=now,
            ))
        return
    call_log = CallLog.query.filter_by(call_id=call_id).first()
    if call_log is None or {call_log.caller_id, call_log.receiver_id} != {caller.id, receiver.id}:
        return
    if signal_type == 'answer' and call_log.status == 'ringing':
        call_log.status = 'answered'
        call_log.answered_at = now
    elif signal_type == 'decline' and call_log.status == 'ringing':
        call_log.status = 'declined'
        call_log.ended_at = now
    elif signal_type == 'hangup' and call_log.ended_at is None:
        call_log.status = 'completed' if call_log.answered_at else 'missed'
        call_log.ended_at = now
        if call_log.answered_at:
            call_log.duration_seconds = max(0, int((now - call_log.answered_at).total_seconds()))


def _target_from_username(username):
    return User.query.filter_by(username=(username or '').strip().lstrip('@')).first()


def _typing_state_payload(sender, receiver):
    cutoff = datetime.utcnow() - timedelta(seconds=current_app.config['MOBILE_API_TYPING_TTL_SECONDS'])
    state = TypingState.query.filter_by(sender_id=sender.id, receiver_id=receiver.id).first()
    if state is not None and state.updated_at < cutoff:
        db.session.delete(state)
        db.session.commit()
        state = None
    return {'isTyping': state is not None}


def _create_assistant_reply(user, assistant, user_message):
    """ينشئ رد مساعد أنتر لمسار Messenger من دون التأثير على حفظ رسالة المستخدم."""
    try:
        remember_user_message(user, assistant, user_message.content)
        assistant_reply, public_error = get_assistant_reply(
            user_message.content,
            user=user,
            assistant=assistant,
        )
        assistant_reply = assistant_reply or public_error
        if not assistant_reply:
            return None

        reply = Message(
            sender_id=assistant.id,
            receiver_id=user.id,
            content=assistant_reply,
            parent_id=user_message.id,
        )
        db.session.add(reply)
        db.session.commit()
        remember_assistant_reply(user, assistant, assistant_reply)
        return reply
    except Exception:
        # رسالة المستخدم حُفظت قبل هذا الاستدعاء، لذا لا ينبغي لفشل المساعد أن يلغيها.
        db.session.rollback()
        current_app.logger.exception('تعذر حفظ رد مساعد أنتر عبر الواجهة المحمولة')
        return None


@mobile_api_bp.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    identifier = str(data.get('identifier', '')).strip()
    password = str(data.get('password', ''))
    device_name = str(data.get('deviceName', 'ANTER Messenger')).strip()
    if not identifier or not password or len(identifier) > 120 or len(password) > 256:
        return _json_error('بيانات تسجيل الدخول غير صالحة.', 400)

    user = User.query.filter(
        (User.username == identifier.lstrip('@')) |
        (User.email == identifier.lower()) |
        (User.phone == identifier)
    ).first()
    if user is None or not user.is_active or not user.check_password(password):
        return _json_error('بيانات تسجيل الدخول غير صحيحة.', 401)

    raw_token, token = issue_mobile_token(user, device_name)
    return jsonify({
        'accessToken': raw_token,
        'tokenType': 'Bearer',
        'expiresAt': token.expires_at.isoformat() + 'Z',
        'user': _user_payload(user),
    }), 201


@mobile_api_bp.route('/auth/browser/exchange', methods=['POST'])
def exchange_browser_authorization():
    data = request.get_json(silent=True) or {}
    code = str(data.get('code', '')).strip()
    state = str(data.get('state', '')).strip()
    redirect_uri = str(data.get('redirectUri', '')).strip()
    if redirect_uri != current_app.config['MOBILE_BROWSER_AUTH_REDIRECT_URI']:
        return _json_error('مسار العودة إلى التطبيق غير صالح.', 400)

    issued = exchange_mobile_browser_authorization(code, state, redirect_uri)
    if issued is None:
        return _json_error('رمز الدخول غير صالح أو انتهت صلاحيته. أعد تسجيل الدخول من الموقع.', 401)

    raw_token, token, user = issued
    return jsonify({
        'accessToken': raw_token,
        'tokenType': 'Bearer',
        'expiresAt': token.expires_at.isoformat() + 'Z',
        'user': _user_payload(user),
    }), 201


@mobile_api_bp.route('/auth/logout', methods=['POST'])
@mobile_api_required
def logout():
    revoke_mobile_token(g.mobile_access_token)
    return jsonify({'success': True})


@mobile_api_bp.route('/me', methods=['GET'])
@mobile_api_required
def me():
    return jsonify({'user': _user_payload(g.mobile_user)})


@mobile_api_bp.route('/devices', methods=['GET'])
@mobile_api_required
def list_trusted_devices():
    now = datetime.utcnow()
    tokens = MobileAccessToken.query.filter(
        MobileAccessToken.user_id == g.mobile_user.id,
        MobileAccessToken.revoked_at.is_(None),
        MobileAccessToken.expires_at > now,
    ).order_by(MobileAccessToken.last_used_at.desc(), MobileAccessToken.created_at.desc()).all()
    return jsonify({
        'devices': [_mobile_device_payload(token, g.mobile_access_token.id) for token in tokens]
    })


@mobile_api_bp.route('/devices/<int:device_id>', methods=['DELETE'])
@mobile_api_required
def revoke_trusted_device(device_id):
    token = MobileAccessToken.query.filter_by(
        id=device_id,
        user_id=g.mobile_user.id,
    ).first()
    if token is None or token.revoked_at is not None:
        return _json_error('لم يُعثر على الجهاز المطلوب.', 404)
    was_current_device = token.id == g.mobile_access_token.id
    revoke_mobile_token(token)
    return jsonify({'success': True, 'wasCurrentDevice': was_current_device})


@mobile_api_bp.route('/contacts', methods=['GET'])
@mobile_api_required
def contacts():
    user = g.mobile_user
    following = Follow.query.filter_by(follower_id=user.id).all()
    ids = [row.followed_id for row in following]
    candidates = User.query.filter(User.id.in_(ids)).order_by(User.last_seen.desc()).all() if ids else []
    return jsonify({'contacts': [_user_payload(other) for other in candidates if _is_mutual_follow(user, other)]})


@mobile_api_bp.route('/users/<string:username>', methods=['GET'])
@mobile_api_required
def user_profile(username):
    """عرض بروفايل مستخدم آخر مع حالة المتابعة والحظر."""
    user = g.mobile_user
    other = _target_from_username(username)
    if other is None:
        return _json_error('المستخدم غير موجود.', 404)

    is_following = Follow.query.filter_by(follower_id=user.id, followed_id=other.id).first() is not None
    is_followed_by = Follow.query.filter_by(follower_id=other.id, followed_id=user.id).first() is not None
    is_blocked = UserBlock.query.filter_by(blocker_id=user.id, blocked_id=other.id).first() is not None

    payload = _user_payload(other)
    payload.update({
        'isFollowing': is_following,
        'isFollowedBy': is_followed_by,
        'isBlocked': is_blocked,
        'isMutual': is_following and is_followed_by,
        'isSelf': other.id == user.id,
    })
    return jsonify({'user': payload})


@mobile_api_bp.route('/users/<string:username>/report', methods=['POST'])
@mobile_api_required
def report_user(username):
    """بلاغ عن مستخدم — يُخزَّن في جدول Report بنمط user-report:<reason>."""
    user = g.mobile_user
    other = _target_from_username(username)
    if other is None:
        return _json_error('المستخدم غير موجود.', 404)
    if other.id == user.id:
        return _json_error('لا يمكنك الإبلاغ عن نفسك.', 400)

    data = request.get_json(silent=True) or {}
    reason = (data.get('reason') or '').strip()
    details = (data.get('details') or '').strip()
    if not reason:
        return _json_error('الرجاء تحديد سبب الإبلاغ.', 400)
    if len(reason) > 100:
        reason = reason[:100]
    if len(details) > 2000:
        details = details[:2000]

    existing = Report.query.filter(
        Report.reporter_id == user.id,
        Report.reason.like('user-report:%'),
        Report.status == 'pending',
    ).filter(Report.details.like(f'%[بلاغ عن مستخدم: {other.username}]%')).first()
    if existing is not None:
        return _json_error('لديك بلاغ معلّق بالفعل عن هذا المستخدم.', 409)

    report = Report(
        reporter_id=user.id,
        reason=f'user-report:{reason}',
        details=f'[بلاغ عن مستخدم: {other.username}]\n{details}',
    )
    db.session.add(report)
    db.session.commit()
    return jsonify({'success': True, 'reportId': report.id}), 201


@mobile_api_bp.route('/conversations', methods=['GET'])
@mobile_api_required
def conversations():
    user = g.mobile_user
    message_rows = Message.query.filter(
        or_(Message.sender_id == user.id, Message.receiver_id == user.id)
    ).order_by(Message.created_at.desc()).all()
    latest_by_other = {}
    for message in message_rows:
        if message.is_deleted_everyone:
            continue
        other_id = message.receiver_id if message.sender_id == user.id else message.sender_id
        if other_id not in latest_by_other:
            latest_by_other[other_id] = message

    users = User.query.filter(User.id.in_(latest_by_other.keys())).all() if latest_by_other else []
    result = []
    for other in users:
        if not _is_mutual_follow(user, other):
            continue
        latest = latest_by_other[other.id]
        unread_count = Message.query.filter_by(receiver_id=user.id, sender_id=other.id, is_read=False, deleted_by_receiver=False).count()
        result.append({
            'user': _user_payload(other),
            'latestMessage': _message_payload(latest),
            'unreadCount': unread_count,
            'isMuted': _is_muted(user, other),
        })
    result.sort(key=lambda item: item['latestMessage']['createdAt'], reverse=True)
    return jsonify({'conversations': result})


@mobile_api_bp.route('/conversations/<string:username>/messages', methods=['GET'])
@mobile_api_required
def list_messages(username):
    user = g.mobile_user
    other = _target_from_username(username)
    if other is None:
        return _json_error('المستخدم غير موجود.', 404)
    if not _is_mutual_follow(user, other):
        return _json_error('تتطلب المحادثة متابعة متبادلة بين الحسابين.', 403)
    after_id = request.args.get('afterId', type=int) or 0
    visible_to_user = or_(
        (Message.sender_id == user.id) & (Message.receiver_id == other.id) & (Message.deleted_by_sender == False),
        (Message.sender_id == other.id) & (Message.receiver_id == user.id) & (Message.deleted_by_receiver == False),
    )
    rows = Message.query.filter(
        visible_to_user,
        Message.id > max(after_id, 0),
        Message.is_deleted_everyone == False,
    ).order_by(Message.id.asc()).limit(100).all()
    changed = False
    for message in rows:
        if message.receiver_id == user.id and not message.is_read:
            message.is_read = True
            changed = True
    if changed:
        db.session.commit()
    return jsonify({'user': _user_payload(other), 'messages': [_message_payload(row) for row in rows]})


@mobile_api_bp.route('/conversations/<string:username>/activity', methods=['GET'])
@mobile_api_required
def conversation_activity(username):
    user = g.mobile_user
    other = _target_from_username(username)
    if other is None:
        return _json_error('المستخدم غير موجود.', 404)
    if not _is_mutual_follow(user, other):
        return _json_error('تتطلب المحادثة متابعة متبادلة بين الحسابين.', 403)
    return jsonify(_typing_state_payload(other, user))


@mobile_api_bp.route('/conversations/<string:username>/safety', methods=['GET'])
@mobile_api_required
def conversation_safety(username):
    user = g.mobile_user
    other = _target_from_username(username)
    if other is None:
        return _json_error('المستخدم غير موجود.', 404)
    return jsonify({
        'isMuted': _is_muted(user, other),
        'hasBlocked': UserBlock.query.filter_by(blocker_id=user.id, blocked_id=other.id).first() is not None,
        'canMessage': _is_mutual_follow(user, other),
    })


@mobile_api_bp.route('/conversations/<string:username>/block', methods=['POST'])
@mobile_api_required
def set_conversation_block(username):
    user = g.mobile_user
    other = _target_from_username(username)
    if other is None:
        return _json_error('المستخدم غير موجود.', 404)
    data = request.get_json(silent=True) or {}
    should_block = data.get('blocked') is not False
    try:
        changed = block_user(user, other) if should_block else unblock_user(user, other)
        db.session.commit()
    except ValueError as error:
        return _json_error(str(error), 400)
    except Exception:
        db.session.rollback()
        current_app.logger.exception('تعذر تحديث الحظر عبر الواجهة المحمولة')
        return _json_error('تعذر تحديث الحظر حالياً.', 500)
    return jsonify({'success': True, 'blocked': should_block, 'changed': changed})


@mobile_api_bp.route('/conversations/<string:username>/mute', methods=['POST'])
@mobile_api_required
def set_conversation_mute(username):
    user = g.mobile_user
    other = _target_from_username(username)
    if other is None:
        return _json_error('المستخدم غير موجود.', 404)
    if user.id == other.id:
        return _json_error('لا يمكن كتم محادثة حسابك نفسه.', 400)
    data = request.get_json(silent=True) or {}
    should_mute = data.get('muted') is not False
    row = MutedConversation.query.filter_by(user_id=user.id, muted_user_id=other.id).first()
    changed = False
    if should_mute and row is None:
        db.session.add(MutedConversation(user_id=user.id, muted_user_id=other.id))
        changed = True
    elif not should_mute and row is not None:
        db.session.delete(row)
        changed = True
    db.session.commit()
    return jsonify({'success': True, 'muted': should_mute, 'changed': changed})


@mobile_api_bp.route('/conversations/<string:username>/assistant-memory/clear', methods=['POST'])
@mobile_api_required
def clear_conversation_assistant_memory(username):
    """يمسح ذاكرة مساعد ANTER للمستخدم صاحب الرمز فقط، لا سجل الرسائل."""
    user = g.mobile_user
    other = _target_from_username(username)
    if other is None:
        return _json_error('المستخدم غير موجود.', 404)
    if not _is_mutual_follow(user, other):
        return _json_error('تتطلب المحادثة متابعة متبادلة بين الحسابين.', 403)
    if not is_anter_assistant(other):
        return _json_error('هذه الميزة متاحة داخل محادثة مساعد أنتر فقط.', 404)
    try:
        clear_memory(user, other)
    except Exception:
        db.session.rollback()
        current_app.logger.exception('تعذر مسح ذاكرة مساعد أنتر عبر الواجهة المحمولة')
        return _json_error('تعذر مسح ذاكرة مساعد أنتر حالياً. حاول مجدداً.', 500)
    return jsonify({'success': True, 'message': 'تم مسح ذاكرة مساعد أنتر. بقي سجل المحادثة كما هو.'})


@mobile_api_bp.route('/conversations/<string:username>/typing', methods=['POST'])
@mobile_api_required
def update_typing_state(username):
    user = g.mobile_user
    other = _target_from_username(username)
    if other is None:
        return _json_error('المستخدم غير موجود.', 404)
    if not _is_mutual_follow(user, other):
        return _json_error('تتطلب المحادثة متابعة متبادلة بين الحسابين.', 403)
    data = request.get_json(silent=True) or {}
    is_typing = data.get('isTyping') is True
    state = TypingState.query.filter_by(sender_id=user.id, receiver_id=other.id).first()
    if is_typing:
        if state is None:
            state = TypingState(sender_id=user.id, receiver_id=other.id)
            db.session.add(state)
        else:
            state.updated_at = datetime.utcnow()
    elif state is not None:
        db.session.delete(state)
    db.session.commit()
    return jsonify({'isTyping': is_typing})


@mobile_api_bp.route('/conversations/<string:username>/messages', methods=['POST'])
@mobile_api_required
def send_message(username):
    user = g.mobile_user
    other = _target_from_username(username)
    if other is None:
        return _json_error('المستخدم غير موجود.', 404)
    if not _is_mutual_follow(user, other):
        return _json_error('يتطلب إرسال الرسالة متابعة متبادلة بين الحسابين.', 403)
    is_multipart = request.mimetype == 'multipart/form-data'
    # DEBUG: نطبع ما يستقبله الخادم
    current_app.logger.info(
        'SEND_DEBUG: mimetype=%s, raw=%r, is_multipart=%s',
        request.mimetype,
        request.get_data(as_text=True)[:500],
        is_multipart,
    )
    data = request.form if is_multipart else (request.get_json(silent=True) or {})
    content = data.get('content', '')
    if not isinstance(content, str):
        return _json_error('محتوى الرسالة غير صالح.', 400)
    content = content.strip()
    if len(content) > current_app.config['MOBILE_API_MAX_MESSAGE_CHARS']:
        return _json_error('الرسالة أطول من الحد المسموح.', 400)
    parent_id = data.get('parentId')
    if parent_id is not None and (not isinstance(parent_id, int) or parent_id < 1):
        return _json_error('الرسالة المرجعية غير صالحة.', 400)
    if parent_id is not None:
        parent = Message.query.filter(
            Message.id == parent_id,
            or_(
                (Message.sender_id == user.id) & (Message.receiver_id == other.id),
                (Message.sender_id == other.id) & (Message.receiver_id == user.id),
            ),
        ).first()
        if parent is None:
            return _json_error('لا يمكنك الرد على رسالة خارج هذه المحادثة.', 403)
    attachment_data = attachment_mime = attachment_name = attachment_kind = None
    if is_multipart and request.files.get('attachment'):
        attachment_data, attachment_mime, attachment_name, attachment_kind = _prepare_mobile_attachment(request.files.get('attachment'))
        if not attachment_data:
            return _json_error('نوع المرفق غير مدعوم أو حجمه أكبر من 8 ميجابايت.', 400)
    if not content and not attachment_data:
        return _json_error('اكتب رسالة أو اختر مرفقاً.', 400)
    message = Message(
        sender_id=user.id,
        receiver_id=other.id,
        content=content or f'مرفق: {attachment_name}',
        parent_id=parent_id,
        attachment_data=attachment_data,
        attachment_mime=attachment_mime,
        attachment_name=attachment_name,
        attachment_kind=attachment_kind,
    )
    db.session.add(message)
    db.session.commit()
    assistant_message = _create_assistant_reply(user, other, message) if is_anter_assistant(other) and not attachment_data else None
    payload = {'message': _message_payload(message)}
    if assistant_message is not None:
        payload['assistantMessage'] = _message_payload(assistant_message)
    return jsonify(payload), 201


@mobile_api_bp.route('/messages/<int:message_id>/attachment', methods=['GET'])
@mobile_api_required
def download_message_attachment(message_id):
    message = Message.query.get(message_id)
    if message is None or not message.attachment_data:
        return _json_error('المرفق غير موجود.', 404)
    if g.mobile_user.id not in {message.sender_id, message.receiver_id}:
        return _json_error('غير مصرح لك بالوصول إلى هذا المرفق.', 403)
    filename = secure_filename(message.attachment_name or f'attachment-{message.id}')
    return Response(
        message.attachment_data,
        mimetype=message.attachment_mime or 'application/octet-stream',
        headers={
            'Content-Length': str(len(message.attachment_data)),
            'Content-Disposition': f"attachment; filename*=UTF-8''{filename}",
            'Cache-Control': 'private, max-age=300',
        },
    )


@mobile_api_bp.route('/calls', methods=['GET'])
@mobile_api_required
def list_mobile_call_logs():
    user = g.mobile_user
    rows = CallLog.query.filter(
        or_(CallLog.caller_id == user.id, CallLog.receiver_id == user.id)
    ).order_by(CallLog.started_at.desc()).limit(100).all()
    result = []
    for row in rows:
        other_id = row.receiver_id if row.caller_id == user.id else row.caller_id
        other = db.session.get(User, other_id)
        if other is None:
            continue
        result.append({
            'id': row.id,
            'callId': row.call_id,
            'otherUser': _user_payload(other),
            'direction': 'outgoing' if row.caller_id == user.id else 'incoming',
            'callType': row.call_type,
            'status': row.status,
            'startedAt': row.started_at.isoformat() + 'Z',
            'durationSeconds': row.duration_seconds,
        })
    return jsonify({'calls': result})


@mobile_api_bp.route('/calls/<string:username>/signal', methods=['POST'])
@mobile_api_required
def send_mobile_call_signal(username):
    caller = g.mobile_user
    receiver = _target_from_username(username)
    if receiver is None:
        return _json_error('المستخدم غير موجود.', 404)
    if not _is_mutual_follow(caller, receiver):
        return _json_error('يتطلب الاتصال متابعة متبادلة بين الحسابين.', 403)
    data = request.get_json(silent=True) or {}
    call_id = str(data.get('callId', '')).strip()
    signal_type = str(data.get('type', '')).strip().lower()
    payload = data.get('payload') if isinstance(data.get('payload'), dict) else {}
    if not call_id or len(call_id) > 64 or signal_type not in {'invite', 'answer', 'decline', 'hangup'}:
        return _json_error('بيانات المكالمة غير صالحة.', 400)
    _update_mobile_call_log(caller, receiver, call_id, signal_type, payload)
    db.session.add(CallSignal(
        call_id=call_id,
        signal_type=signal_type,
        payload=json.dumps(payload, ensure_ascii=False),
        sender_id=caller.id,
        receiver_id=receiver.id,
    ))
    db.session.commit()
    return jsonify({'success': True, 'callId': call_id, 'type': signal_type})


@mobile_api_bp.route('/messages/<int:message_id>', methods=['DELETE'])
@mobile_api_required
def delete_message(message_id):
    user = g.mobile_user
    message = Message.query.get(message_id)
    if message is None:
        return _json_error('الرسالة غير موجودة.', 404)
    if user.id not in {message.sender_id, message.receiver_id}:
        return _json_error('غير مصرح لك بحذف هذه الرسالة.', 403)
    data = request.get_json(silent=True) or {}
    scope = data.get('scope', 'me')
    if scope not in {'me', 'everyone'}:
        return _json_error('نطاق الحذف غير صالح.', 400)
    if scope == 'everyone':
        if message.sender_id != user.id:
            return _json_error('لا يمكنك حذف رسالة غير مرسلة منك عند الجميع.', 403)
        message.is_deleted_everyone = True
    elif message.sender_id == user.id:
        message.deleted_by_sender = True
    else:
        message.deleted_by_receiver = True
    db.session.commit()
    return jsonify({'success': True, 'scope': scope})


@mobile_api_bp.route('/messages/<int:message_id>/forward', methods=['POST'])
@mobile_api_required
def forward_message(message_id):
    user = g.mobile_user
    original = Message.query.get(message_id)
    if original is None:
        return _json_error('الرسالة غير موجودة.', 404)
    if user.id not in {original.sender_id, original.receiver_id}:
        return _json_error('غير مصرح لك بإعادة توجيه هذه الرسالة.', 403)
    if original.is_deleted_everyone:
        return _json_error('لا يمكن إعادة توجيه رسالة محذوفة عند الجميع.', 409)
    data = request.get_json(silent=True) or {}
    target_username = data.get('targetUsername')
    if not isinstance(target_username, str) or not target_username.strip():
        return _json_error('يجب تحديد مستلم الرسالة.', 400)
    target = _target_from_username(target_username)
    if target is None:
        return _json_error('المستخدم غير موجود.', 404)
    if not _is_mutual_follow(user, target):
        return _json_error('تتطلب إعادة التوجيه متابعة متبادلة مع المستلم.', 403)
    forwarded = Message(
        sender_id=user.id,
        receiver_id=target.id,
        content=original.content,
        audio_data=original.audio_data,
        audio_mime=original.audio_mime,
        attachment_data=original.attachment_data,
        attachment_mime=original.attachment_mime,
        attachment_name=original.attachment_name,
        attachment_kind=original.attachment_kind,
    )
    db.session.add(forwarded)
    db.session.commit()
    return jsonify({'success': True, 'message': _message_payload(forwarded)}), 201


@mobile_api_bp.route('/messages/<int:message_id>/report', methods=['POST'])
@mobile_api_required
def report_message(message_id):
    user = g.mobile_user
    message = Message.query.get(message_id)
    if message is None:
        return _json_error('الرسالة غير موجودة.', 404)
    if user.id not in {message.sender_id, message.receiver_id}:
        return _json_error('لا يمكنك الإبلاغ عن رسالة خارج محادثتك.', 403)
    data = request.get_json(silent=True) or {}
    reason = str(data.get('reason', '')).strip().lower()
    details = str(data.get('details', '')).strip()
    if reason not in {'spam', 'harassment', 'inappropriate', 'other'}:
        return _json_error('يرجى اختيار سبب صحيح للبلاغ.', 400)
    if len(details) > 1000:
        return _json_error('تفاصيل البلاغ طويلة جداً.', 400)
    if Report.query.filter_by(reporter_id=user.id, message_id=message.id).first() is not None:
        return _json_error('لقد أرسلت بلاغاً عن هذه الرسالة سابقاً.', 409)
    db.session.add(Report(
        reporter_id=user.id,
        message_id=message.id,
        reason=reason,
        details=details,
        status='pending',
    ))
    db.session.commit()
    return jsonify({'success': True, 'message': 'تم إرسال البلاغ للمراجعة.'}), 201


# ============================================================
# ANTER: اقتراح متابعة من جهات اتصال الهاتف (Contacts Matching)
# ------------------------------------------------------------
# يستقبل قائمة أرقام هواتف (من تطبيق ANTER Messenger) ويعيد
# المستخدمين المطابقين. لا يُخزّن الأرقام، ولا يكشف غير المسجّلين.
# ============================================================

import re as _re

_PHONE_CLEAN_RE = _re.compile(r'[^\d+]')


def _normalize_phone(raw):
    """يوحّد صيغة الرقم: +<digits> بدون مسافات/رموز. يعيد '' إذا غير صالح."""
    if not raw:
        return ''
    s = str(raw).strip()
    # إزالة المسافات والشرطات والأقواس
    s = _PHONE_CLEAN_RE.sub('', s)
    # معالجة البدايات المختلفة
    if s.startswith('00'):
        s = '+' + s[2:]
    if not s.startswith('+'):
        s = '+' + s
    # يجب أن يكون 8 إلى 15 رقمًا (معيار E.164)
    digits = s[1:]
    if not digits.isdigit() or not (8 <= len(digits) <= 15):
        return ''
    return s


@mobile_api_bp.route('/suggested-follows', methods=['POST'])
@mobile_api_required
def suggested_follows_from_contacts():
    """
    POST /api/mobile/v1/suggested-follows
    Body: { "phones": ["+967...", "00967...", "737..."] }

    يعيد: { "suggested": [ { "phone": "...", "user": {...}, "isFollowing": false } ] }
    """
    user = g.mobile_user
    data = request.get_json(silent=True) or {}
    raw_phones = data.get('phones')

    if not isinstance(raw_phones, list):
        return _json_error('يجب إرسال قائمة أرقام في الحقل phones.', 400)
    if len(raw_phones) > 500:
        return _json_error('عدد الأرقام كبير جدًا (الحد 500).', 400)

    # تطبيع + إزالة المكرر
    normalized = {}
    for raw in raw_phones:
        norm = _normalize_phone(raw)
        if norm:
            normalized[norm] = True
    if not normalized:
        return jsonify({'suggested': [], 'matched': 0})

    phones = list(normalized.keys())

    # جلب المستخدمين المطابقين
    candidates = User.query.filter(User.phone.in_(phones)).all()

    # جلب من يتابعهم المستخدم حاليًا لتفادي التكرار
    already_following = {
        row.followed_id
        for row in Follow.query.filter_by(follower_id=user.id).all()
    }

    # جلب المحظورين (في الاتجاهين)
    blocked_ids = {
        row.blocked_id
        for row in UserBlock.query.filter_by(blocker_id=user.id).all()
    }
    blocked_ids.update(
        row.blocker_id
        for row in UserBlock.query.filter_by(blocked_id=user.id).all()
    )

    suggested = []
    for other in candidates:
        if other.id == user.id:
            continue
        if other.id in blocked_ids:
            continue
        # نُرجع حتى المتابَعين — لكن نضع علامة isFollowing
        suggested.append({
            'phone': other.phone,
            'user': _user_payload(other),
            'isFollowing': other.id in already_following,
        })

    # الترتيب: غير المتابَعين أولًا، ثم النشطون
    suggested.sort(key=lambda item: (
        item['isFollowing'],
        not item['user'].get('isOnline'),
    ))

    return jsonify({
        'suggested': suggested,
        'matched': len(suggested),
        'submitted': len(phones),
    })
