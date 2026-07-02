from flask import Blueprint, render_template, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Notification

notifications_bp = Blueprint('notifications', __name__, url_prefix='/notifications')

@notifications_bp.route('/')
@login_required
def index():
    # جلب جميع الإشعارات
    notifs = current_user.notifications.order_by(Notification.created_at.desc()).all()
    
    # تعيين جميع الإشعارات غير المقروءة إلى مقروءة
    for n in notifs:
        if not n.is_read:
            n.is_read = True
    db.session.commit()
    
    return render_template('notifications.html', notifications=notifs)

@notifications_bp.route('/unread_count')
@login_required
def unread_count():
    count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return jsonify({'count': count})

@notifications_bp.route('/mark_read/<int:notification_id>', methods=['POST'])
@login_required
def mark_read(notification_id):
    """تحديد إشعار واحد كمقروء عند النقر عليه"""
    notification = Notification.query.get_or_404(notification_id)
    if notification.user_id == current_user.id:
        notification.is_read = True
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False}), 403
