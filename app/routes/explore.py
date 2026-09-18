from datetime import datetime, timedelta

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app.models import User, Follow, Post, Hashtag
from app.extensions import db
from app.utils.media_urls import avatar_url
from app.services.geo_ranker import geo_score_for_user
from sqlalchemy import func

explore_bp = Blueprint('explore', __name__, url_prefix='/explore')


@explore_bp.route('/')
@login_required
def explore():
    # المتابعين الحاليين (بما فيهم المستخدم نفسه لاستبعادهم لاحقاً)
    following_ids = [f.followed_id for f in current_user.following] + [current_user.id]

    # المستخدمون من الدرجة الثانية (أصدقاء الأصدقاء)
    second_degree = db.session.query(
        Follow.followed_id,
        func.count(Follow.follower_id).label('mutual_count')
    ).filter(
        Follow.follower_id.in_(following_ids),
        ~Follow.followed_id.in_(following_ids)
    ).group_by(Follow.followed_id).order_by(
        func.count(Follow.follower_id).desc()
    ).limit(15).all()

    suggested_ids = [row[0] for row in second_degree]
    mutual_counts = {row[0]: row[1] for row in second_degree}

    # إذا كانت قائمة الدرجة الثانية فارغة، اعرض مستخدمين لديهم منشورات حديثة.
    if not suggested_ids:
        recent_cutoff = datetime.utcnow() - timedelta(days=30)
        active_users = db.session.query(
            Post.author_id,
            func.count(Post.id).label('posts_count')
        ).filter(
            Post.created_at > recent_cutoff,
            ~Post.author_id.in_(following_ids)
        ).group_by(Post.author_id).order_by(
            func.count(Post.id).desc()
        ).limit(30).all()
        suggested_ids = [row[0] for row in active_users]
        mutual_counts = {row[0]: 0 for row in active_users}

    # ANTER: نُوسّع القائمة ثم نُعيد ترتيبها بمعيار مركّب
    # (أصدقاء مشتركون + النقاط الجغرافية). كل 5 أصدقاء مشتركين = نفس وزن نفس الدولة.
    users_by_id = {
        user.id: user
        for user in User.query.filter(User.id.in_(suggested_ids[:30])).all()
    }

    def _suggest_score(uid):
        u = users_by_id.get(uid)
        if not u:
            return -1.0
        mutual = mutual_counts.get(uid, 0) or 0
        geo = geo_score_for_user(u, current_user)
        return mutual * 5.0 + geo

    ranked_ids = sorted(
        [uid for uid in suggested_ids if uid in users_by_id],
        key=_suggest_score,
        reverse=True,
    )

    suggested_users = [users_by_id[uid] for uid in ranked_ids[:20]]

    return render_template('explore.html', users=suggested_users)


@explore_bp.route('/search')
@login_required
def search():
    q = request.args.get('q', '').strip()
    if q:
        users = User.query.filter(
            (User.username.contains(q)) | (User.name.contains(q))
        ).filter(User.id != current_user.id).limit(20).all()
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
        'is_following': current_user.is_following(u)
    } for u in users])


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
