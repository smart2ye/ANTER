from flask import Blueprint, render_template, jsonify, redirect, url_for, flash, request, current_app
import json
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Notification

notifications_bp = Blueprint('notifications', __name__, url_prefix='/notifications')

@notifications_bp.route('/')
@login_required
def index():
    """صفحة الإشعارات — لا تُعلّم الكل مقروء تلقائيًا (ANTER)."""
    notifs = (
        current_user.notifications
        .order_by(Notification.created_at.desc())
        .limit(200)
        .all()
    )
    # ANTER: لا نُظهر إشعارات صادرة من حسابات محذوفة.
    notifs = [
        n for n in notifs
        if not getattr(n.actor, 'is_deleted', False)
    ]

    unread_count = sum(1 for n in notifs if not n.is_read)

    return render_template(
        'notifications.html',
        notifications=notifs,
        unread_count=unread_count,
    )


@notifications_bp.route('/unread_count')
@login_required
def unread_count():
    # ANTER: نستبعد إشعارات المحذوفين من العدّاد ليتوافق مع قائمة الصفحة.
    from app.models import User
    count = (
        Notification.query
        .join(User, User.id == Notification.actor_id)
        .filter(
            Notification.user_id == current_user.id,
            Notification.is_read.is_(False),
            User.is_deleted.is_(False),
        )
        .count()
    )
    return jsonify({'count': count})

@notifications_bp.route('/latest')
@login_required
def latest():
    """آخر إشعار غير مقروء — لعرضه في البطاقة المنبثقة."""
    from app.models import User
    notif = (
        Notification.query
        .join(User, User.id == Notification.actor_id)
        .filter(
            Notification.user_id == current_user.id,
            Notification.is_read.is_(False),
            User.is_deleted.is_(False),
        )
        .order_by(Notification.created_at.desc())
        .first()
    )
    if not notif:
        return jsonify({'ok': False})

    actor = notif.actor
    actor_name = (actor.name or actor.username) if actor else 'شخص ما'
    action = notif.action or ''

    mapping = {
        'like': f'أعجب {actor_name} بمنشورك',
        'like_comment': f'أعجب {actor_name} بتعليقك',
        'like_video': f'أعجب {actor_name} بمقطعك',
        'comment': f'علّق {actor_name} على منشورك',
        'comment_video': f'علّق {actor_name} على مقطعك',
        'reply': f'ردّ {actor_name} عليك',
        'reply_video': f'ردّ {actor_name} على تعليقك',
        'follow': f'بدأ {actor_name} بمتابعتك',
        'message': f'أرسل لك {actor_name} رسالة',
        'voice_message': f'أرسل لك {actor_name} رسالة صوتية',
        'file_message': f'أرسل لك {actor_name} ملفًا',
        'voice_call': f'اتصل بك {actor_name} صوتيًا',
        'wall_post': f'كتب {actor_name} على حائطك',
        'mention': f'أشار إليك {actor_name}',
        'mention_post': f'ذكرك {actor_name} في منشور',
        'mention_comment': f'ذكرك {actor_name} في تعليق',
        'mention_group_post': f'ذكر {actor_name} متابعيه في منشور',
        'mention_group_comment': f'ذكر {actor_name} متابعيه في تعليق',
        'mention_all_post': f'وجه {actor_name} رسالة للجميع في منشور',
        'mention_all_comment': f'وجه {actor_name} رسالة للجميع في تعليق',
        'repost': f'أعاد {actor_name} نشر منشورك',
        'founder_post': 'رسالة جديدة من المؤسس',
        'early_member': 'تم تكريمك كعضو مبكّر 🌟',
        'early_member_revoked': 'تم إلغاء شارة العضو المبكّر',
        'verification_approved': 'تم توثيق حسابك ✓',
        'verification_rejected': 'لم يُقبل طلب التوثيق',
        'report_resolved': 'تمت مراجعة بلاغك',
        'report_rejected': 'تم رفض بلاغك',
        'story_issue_fixed': 'إصلاح مشكلة تقنية في القصة',
        'terms_update': 'تم تحديث الشروط والأحكام',
        'video_lost': 'تعذّر العثور على فيديو',
    }
    text = mapping.get(action)
    if not text and notif.extra_text:
        text = notif.extra_text
    if not text:
        text = 'لديك إشعار جديد'

    return jsonify({
        'ok': True,
        'id': notif.id,
        'action': action,
        'text': text,
        'actor_name': actor_name,
    })


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

@notifications_bp.route('/subscribe', methods=['POST'])
@login_required
def subscribe():
    """تسجيل اشتراك الإشعارات (من Service Worker)"""
    from app.models import PushSubscription
    data = request.get_json()
    endpoint = data.get('endpoint')
    p256dh = data.get('keys', {}).get('p256dh')
    auth = data.get('keys', {}).get('auth')

    if not all([endpoint, p256dh, auth]):
        return jsonify({'success': False, 'message': 'بيانات ناقصة'}), 400

    # حذف الاشتراك القديم (إن وجد)
    PushSubscription.query.filter_by(endpoint=endpoint).delete()

    sub = PushSubscription(
        user_id=current_user.id,
        endpoint=endpoint,
        p256dh=p256dh,
        auth=auth
    )
    db.session.add(sub)
    db.session.commit()
    return jsonify({'success': True})

@notifications_bp.route('/unsubscribe', methods=['POST'])
@login_required
def unsubscribe():
    """إلغاء اشتراك الإشعارات"""
    from app.models import PushSubscription
    data = request.get_json()
    endpoint = data.get('endpoint')
    if endpoint:
        PushSubscription.query.filter_by(endpoint=endpoint, user_id=current_user.id).delete()
        db.session.commit()
    return jsonify({'success': True})

@notifications_bp.route('/mark_all_read', methods=['POST'])
@login_required
def mark_all_read():
    """تحديد كل إشعارات المستخدم كمقروءة."""
    Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False,
    ).update({'is_read': True}, synchronize_session=False)
    db.session.commit()
    return jsonify({'success': True})


@notifications_bp.route('/mark_unread/<int:notification_id>', methods=['POST'])
@login_required
def mark_unread(notification_id):
    """إعادة إشعار إلى "غير مقروء"."""
    n = Notification.query.get_or_404(notification_id)
    if n.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'غير مصرح'}), 403

    n.is_read = False
    db.session.commit()
    return jsonify({'success': True})


@notifications_bp.route('/delete/<int:notification_id>', methods=['POST'])
@login_required
def delete_notification(notification_id):
    """حذف إشعار واحد."""
    n = Notification.query.get_or_404(notification_id)
    if n.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'غير مصرح'}), 403

    db.session.delete(n)
    db.session.commit()
    return jsonify({'success': True})


def send_push_notification(user_id, title, body, icon='/static/icons/anter-icon-512.png'):
    """إرسال إشعار push لمستخدم معين"""
    from app.models import PushSubscription
    from pywebpush import webpush, WebPushException
    import os

    subscriptions = PushSubscription.query.filter_by(user_id=user_id).all()
    if not subscriptions:
        return

    vapid_private_key = os.environ.get('VAPID_PRIVATE_KEY')
    vapid_public_key = os.environ.get('VAPID_PUBLIC_KEY')

    if not vapid_private_key or not vapid_public_key:
        current_app.logger.warning('VAPID keys not configured — push notifications disabled')
        return

    for sub in subscriptions:
        try:
            webpush(
                subscription_info=sub.to_dict(),
                data=json.dumps({
                    'title': title,
                    'body': body,
                    'icon': icon,
                    'badge': '/static/uploads/default.png'
                }, ensure_ascii=False),
                vapid_private_key=vapid_private_key,
                vapid_claims={'sub': 'mailto:smart2ye@gmail.com'}
            )
        except WebPushException as e:
            if '410' in str(e) or '404' in str(e):
                # الاشتراك منتهي الصلاحية
                db.session.delete(sub)
                db.session.commit()
            else:
                current_app.logger.warning('Push error: %s', e)
