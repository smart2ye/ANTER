from datetime import datetime, timedelta

from flask import Blueprint, current_app, g, jsonify, request
from sqlalchemy import or_

from app.extensions import csrf, db
from app.models import Follow, Message, TypingState, User
from app.services.anter_assistant import get_assistant_reply, is_anter_assistant
from app.services.anter_memory import clear_memory, remember_assistant_reply, remember_user_message
from app.services.mobile_api_auth import issue_mobile_token, mobile_api_required, revoke_mobile_token


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
    }


def _is_mutual_follow(user, other):
    return user.id != other.id and user.is_following(other) and other.is_following(user)


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
    }


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


@mobile_api_bp.route('/auth/logout', methods=['POST'])
@mobile_api_required
def logout():
    revoke_mobile_token(g.mobile_access_token)
    return jsonify({'success': True})


@mobile_api_bp.route('/me', methods=['GET'])
@mobile_api_required
def me():
    return jsonify({'user': _user_payload(g.mobile_user)})


@mobile_api_bp.route('/contacts', methods=['GET'])
@mobile_api_required
def contacts():
    user = g.mobile_user
    following = Follow.query.filter_by(follower_id=user.id).all()
    ids = [row.followed_id for row in following]
    candidates = User.query.filter(User.id.in_(ids)).order_by(User.last_seen.desc()).all() if ids else []
    return jsonify({'contacts': [_user_payload(other) for other in candidates if _is_mutual_follow(user, other)]})


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
    data = request.get_json(silent=True) or {}
    content = data.get('content')
    if not isinstance(content, str):
        return _json_error('محتوى الرسالة غير صالح.', 400)
    content = content.strip()
    if not content or len(content) > current_app.config['MOBILE_API_MAX_MESSAGE_CHARS']:
        return _json_error('يجب أن تكون الرسالة بين 1 و2000 حرف.', 400)
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
    message = Message(sender_id=user.id, receiver_id=other.id, content=content, parent_id=parent_id)
    db.session.add(message)
    db.session.commit()
    assistant_message = _create_assistant_reply(user, other, message) if is_anter_assistant(other) else None
    payload = {'message': _message_payload(message)}
    if assistant_message is not None:
        payload['assistantMessage'] = _message_payload(assistant_message)
    return jsonify(payload), 201


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
