from app.utils.helpers import get_status_icon
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.extensions import db, csrf
from app.models import Message, User, Notification

messages_bp = Blueprint('messages', __name__, url_prefix='/messages')

@messages_bp.route('/')
@login_required
def inbox():
    # قائمة المحادثات (آخر رسالة لكل مستخدم)
    users = User.query.filter(User.id != current_user.id).all()
    conversations = []
    for u in users:
        last_msg = Message.query.filter(
            ((Message.sender_id == current_user.id) & (Message.receiver_id == u.id)) |
            ((Message.sender_id == u.id) & (Message.receiver_id == current_user.id))
        ).order_by(Message.created_at.desc()).first()
        if last_msg:
            conversations.append((u, last_msg))
    conversations.sort(key=lambda x: x[1].created_at, reverse=True)
    return render_template('messages/inbox.html', conversations=conversations, get_status_icon=get_status_icon)

@messages_bp.route('/<int:user_id>')
@login_required
def chat(user_id):
    other = User.query.get_or_404(user_id)
    messages = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == other.id)) |
        ((Message.sender_id == other.id) & (Message.receiver_id == current_user.id))
    ).order_by(Message.created_at.asc()).all()
    # تعيين الرسائل كمقروءة
    for m in messages:
        if m.receiver_id == current_user.id and not m.is_read:
            m.is_read = True
    db.session.commit()
    return render_template('messages/chat.html', other=other, messages=messages, get_status_icon=get_status_icon)

@messages_bp.route('/send/<int:user_id>', methods=['POST'])
@login_required
@csrf.exempt  # تجنب خطأ 400
def send(user_id):
    other = User.query.get_or_404(user_id)
    content = request.form.get('content', '').strip()
    if content:
        msg = Message(sender_id=current_user.id, receiver_id=other.id, content=content)
        db.session.add(msg)
        # إشعار للمستقبل
        notif = Notification(user_id=other.id, actor_id=current_user.id, action='message')
        db.session.add(notif)
        db.session.commit()
        flash('تم إرسال الرسالة.', 'success')
    else:
        flash('الرسالة فارغة.', 'danger')
    return redirect(url_for('messages.chat', user_id=user_id))
