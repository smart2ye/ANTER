from datetime import datetime, timedelta

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app.models import User, Follow, Post, Hashtag
from app.extensions import db
from app.utils.media_urls import avatar_url
from app.services.explore_service import (
    trending_posts,
    trending_reels,
    trending_users,
    search_users,
)
from sqlalchemy import func

explore_bp = Blueprint('explore', __name__, url_prefix='/explore')


@explore_bp.route('/')
@login_required
def explore():
    """صفحة Explore الشاملة — 3 تبويبات + بحث."""
    from app.models import Like, Comment, VideoLike

    # اقتراحات الأشخاص (مع geo)
    suggested_users = trending_users(current_user, limit=20)

    # منشورات رائجة
    posts = trending_posts(current_user, limit=15)

    # ريلز رائجة
    reels = trending_reels(current_user, limit=15)

    # ANTER: batch — تجميع البيانات بدل N+1 لكل عنصر في القالب
    following_ids = {f.followed_id for f in current_user.following}

    user_ids = [u.id for u in suggested_users]
    if user_ids:
        rows = (
            db.session.query(Follow.followed_id, func.count(Follow.id))
            .filter(Follow.followed_id.in_(user_ids))
            .group_by(Follow.followed_id).all()
        )
        follower_counts = {uid: cnt for uid, cnt in rows}
    else:
        follower_counts = {}

    post_ids = [p.id for p in posts]
    if post_ids:
        rows = (
            db.session.query(Like.post_id, func.count(Like.id))
            .filter(Like.post_id.in_(post_ids))
            .group_by(Like.post_id).all()
        )
        post_likes = {pid: cnt for pid, cnt in rows}

        rows = (
            db.session.query(Comment.post_id, func.count(Comment.id))
            .filter(Comment.post_id.in_(post_ids))
            .group_by(Comment.post_id).all()
        )
        post_comments = {pid: cnt for pid, cnt in rows}
    else:
        post_likes = {}
        post_comments = {}

    reel_ids = [r.id for r in reels]
    if reel_ids:
        rows = (
            db.session.query(VideoLike.video_id, func.count(VideoLike.id))
            .filter(VideoLike.video_id.in_(reel_ids))
            .group_by(VideoLike.video_id).all()
        )
        reel_likes = {vid: cnt for vid, cnt in rows}
    else:
        reel_likes = {}

    return render_template(
        'explore.html',
        users=suggested_users,
        posts=posts,
        reels=reels,
        following_ids=following_ids,
        follower_counts=follower_counts,
        post_likes=post_likes,
        post_comments=post_comments,
        reel_likes=reel_likes,
    )


@explore_bp.route('/search')
@login_required
def search():
    """بحث في المستخدمين فقط (يُستخدم من JS الحالي)."""
    q = request.args.get('q', '').strip()
    if q:
        users = User.query.filter(
            (User.username.contains(q)) | (User.name.contains(q))
        ).filter(
            User.id != current_user.id,
            User.is_deleted.is_(False),
        ).limit(20).all()
    else:
        users = []
    return jsonify([{
        'id': u.id,
        'username': u.username,
        'name': u.name,
        'bio': u.bio,
        'avatar': u.avatar,
        'avatar_url': avatar_url(u),
        'followers_count': u.follower_count(),
        'is_following': current_user.is_following(u),
    } for u in users])


@explore_bp.route('/search-all')
@login_required
def search_all():
    """ANTER: بحث شامل — منشورات + ريلز + أشخاص."""
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({'posts': [], 'reels': [], 'users': []})

    posts = trending_posts(current_user, limit=15, query=q, hours=24*30)
    reels = trending_reels(current_user, limit=15, query=q, days=90)
    users = search_users(current_user, q, limit=15)

    return jsonify({
        'posts': [{
            'id': p.id,
            'public_id': p.public_id,
            'content': (p.content or '')[:200],
            'author_username': p.author.username,
            'author_name': p.author.name,
            'url': f'/p/{p.public_id}',
        } for p in posts],
        'reels': [{
            'id': v.id,
            'public_id': v.public_id,
            'title': v.title,
            'author_username': v.author.username,
            'url': f'/videos/r/{v.public_id}',
        } for v in reels],
        'users': [{
            'id': u.id,
            'username': u.username,
            'name': u.name,
            'avatar_url': avatar_url(u),
            'is_following': current_user.is_following(u),
        } for u in users],
    })


@explore_bp.route('/hashtag/<string:tag>')
@login_required
def hashtag(tag):
    """عرض منشورات وسم محدد في صفحة HTML مهيّأة للمستخدم."""
    normalized_tag = tag.strip().lstrip('#').lower()
    hashtag_record = Hashtag.query.filter(func.lower(Hashtag.name) == normalized_tag).first()

    if hashtag_record:
        posts = hashtag_record.posts.order_by(Post.created_at.desc()).all()
    else:
        posts = []

    return render_template(
        'explore/hashtag.html',
        tag=normalized_tag,
        posts=posts,
    )
