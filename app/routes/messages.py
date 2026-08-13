from app.utils.helpers import get_status_icon
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.extensions import db, csrf
from app.models import Message, User, Notification
from sqlalchemy import or_

messages_bp = Blueprint('messages', __name__, url_prefix='/messages')


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
        other_id = (
            message.receiver_id
            if message.sender_id == current_user.id
            else message.sender_id
        )
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

    # تعيين الرسائل كمقروءة
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
    )


@messages_bp.route('/send/<int:user_id>', methods=['POST'])
@login_required
@csrf.exempt  # تجنب خطأ 400

def send(user_id):
    other = User.query.get_or_404(user_id)
    content = request.form.get('content', '').strip()
    if content:
        msg = Message(sender_id=current_user.id, receiver_id=other.id, content=content)
        db.session.add(msg)
        notif = Notification(user_id=other.id, actor_id=current_user.id, action='message')
        db.session.add(notif)
        db.session.commit()
        flash('تم إرسال الرسالة.', 'success')
    else:
        flash('الرسالة فارغة.', 'danger')
    return redirect(url_for('messages.chat', user_id=user_id))
