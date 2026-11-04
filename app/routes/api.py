from flask import Blueprint, jsonify, request, url_for, abort
from flask_login import login_required, current_user
from app.models import Post, User, Video, Moment, MomentPost
from app.extensions import db

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/posts')
@login_required
def get_posts():
    """جلب آخر المنشورات (JSON)"""
    posts = Post.query.order_by(Post.created_at.desc()).limit(20).all()
    return jsonify([{
        'id': p.public_id,
        'url': url_for('posts.view_post', public_id=p.public_id),
        'content': p.content,
        'image': p.image,
        'link_preview': {
            'url': p.link_url,
            'title': p.link_title,
            'description': p.link_description,
            'image': p.link_image,
        } if p.link_url else None,
        'created_at': p.created_at.isoformat(),
        'author': {
            'id': p.author.id,
            'username': p.author.username,
            'name': p.author.name,
            'avatar': p.author.avatar
        },
        'likes': p.like_count(),
        'comments': p.comment_count()
    } for p in posts])

@api_bp.route('/users/<username>')
@login_required
def get_user(username):
    """جلب معلومات مستخدم (JSON)"""
    user = User.query.filter_by(username=username).first_or_404()
    if getattr(user, 'is_deleted', False):
        abort(404)
    return jsonify({
        'id': user.id,
        'username': user.username,
        'name': user.name,
        'bio': user.bio,
        'avatar': user.avatar,
        'followers': user.follower_count(),
        'following': user.following_count(),
        'posts': user.posts.count(),
        'is_verified': user.is_verified,
        'is_private': user.is_private
    })

@api_bp.route('/videos/reels')
@login_required
def get_reels():
    """جلب الريلزات (JSON) مع حالة تفاعل المستخدم الحالي."""
    videos = (
        Video.query
        .filter_by(is_reel=True)
        .order_by(Video.created_at.desc())
        .limit(20)
        .all()
    )

    return jsonify([
        {
            'id': v.public_id,
            'video_id': v.id,
            'url': url_for('videos.watch', public_id=v.public_id),
            'title': v.title,
            'description': v.description,
            'thumbnail': v.thumbnail_path,
            'views': v.views,
            'likes': v.like_count(),
            'comments': v.comment_count(),
            'liked': v.likes.filter_by(user_id=current_user.id).first() is not None,
            'duration': v.duration or 0,
            'author': {
                'id': v.author.id,
                'username': v.author.username,
                'name': v.author.name,
                'avatar': v.author.avatar
            }
        }
        for v in videos
    ])


@api_bp.route('/moments')
@login_required
def get_moments():
    """جلب آخر الـ Moments النشطة (JSON)"""
    moments = (
        Moment.query
        .filter_by(status='active')
        .order_by(Moment.updated_at.desc())
        .limit(20)
        .all()
    )

    return jsonify([{
        'id': m.id,
        'title': m.title,
        'description': m.description,
        'cover_media': m.cover_media,
        'status': m.status,
        'created_at': m.created_at.isoformat(),
        'updated_at': m.updated_at.isoformat(),
        'expires_at': m.expires_at.isoformat() if m.expires_at else None,
        'posts_count': m.posts.count()
    } for m in moments])


@api_bp.route('/moments/<int:moment_id>')
@login_required
def get_moment(moment_id):
    """جلب تفاصيل Moment ومنشوراته (JSON)"""
    moment = Moment.query.filter_by(
        id=moment_id,
        status='active'
    ).first_or_404()

    posts = (
        moment.posts
        .join(Post, MomentPost.post_id == Post.id)
        .order_by(Post.created_at.desc())
        .limit(50)
        .all()
    )

    return jsonify({
        'id': moment.id,
        'title': moment.title,
        'description': moment.description,
        'cover_media': moment.cover_media,
        'status': moment.status,
        'created_at': moment.created_at.isoformat(),
        'updated_at': moment.updated_at.isoformat(),
        'expires_at': moment.expires_at.isoformat() if moment.expires_at else None,
        'posts_count': moment.posts.count(),
        'posts': [{
            'id': p.public_id,
            'url': url_for('posts.view_post', public_id=p.public_id),
            'content': p.content,
            'image': p.image,
            'created_at': p.created_at.isoformat(),
            'author': {
                'id': p.author.id,
                'username': p.author.username,
                'name': p.author.name,
                'avatar': p.author.avatar
            },
            'likes': p.like_count(),
            'comments': p.comment_count()
        } for p in posts]
    })


@api_bp.route('/inbox_counts')
@login_required
def inbox_counts():
    """ANTER: عدادات موحّدة (إشعارات + رسائل + حراج) — طلب واحد بدل 3."""
    from app.models import Notification, Message, HarajMessage, User
    from app.services.message_safety import blocked_counterparty_ids
    from app.models import MutedConversation
    from sqlalchemy import func

    HARAJ_ACTIONS = ['haraj_message', 'haraj_comment', 'haraj_rating']
    uid = current_user.id

    # 1. إشعارات عامة (بلا إشعارات المحذوفين)
    notifications = (
        db.session.query(func.count(Notification.id))
        .join(User, User.id == Notification.actor_id)
        .filter(
            Notification.user_id == uid,
            Notification.is_read.is_(False),
            User.is_deleted.is_(False),
        )
        .scalar()
        or 0
    )

    # 2. رسائل غير مقروءة (نستبعد المحجوبين/الصامتين)
    hidden_sender_ids = blocked_counterparty_ids(uid) | {
        row.muted_user_id
        for row in MutedConversation.query.filter_by(user_id=uid).all()
    }
    msg_q = Message.query.filter_by(receiver_id=uid, is_read=False, deleted_by_receiver=False)
    if hidden_sender_ids:
        msg_q = msg_q.filter(Message.sender_id.notin_(hidden_sender_ids))
    messages = msg_q.count()

    # 3. حراج: رسائل + إشعارات
    haraj_messages = HarajMessage.query.filter_by(receiver_id=uid, is_read=False).count()
    haraj_notifications = Notification.query.filter(
        Notification.user_id == uid,
        Notification.action.in_(HARAJ_ACTIONS),
        Notification.is_read.is_(False),
    ).count()

    return jsonify({
        'notifications': notifications,
        'messages': messages,
        'haraj': haraj_messages + haraj_notifications,
        'haraj_messages': haraj_messages,
        'haraj_notifications': haraj_notifications,
    })
