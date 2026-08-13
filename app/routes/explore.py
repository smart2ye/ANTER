from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app.models import User, Follow, Post
from app.extensions import db
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

    # إذا كانت قائمة الدرجة الثانية فارغة، اعرض مستخدمين لديهم منشورات حديثة.
    if not suggested_ids:
        active_users = db.session.query(
            Post.author_id,
            func.count(Post.id).label('posts_count')
        ).filter(
            Post.created_at > func.datetime('now', '-30 days'),
            ~Post.author_id.in_(following_ids)
        ).group_by(Post.author_id).order_by(
            func.count(Post.id).desc()
        ).limit(20).all()
        suggested_ids = [row[0] for row in active_users]

    # استعلام واحد بدلاً من استعلام لكل مستخدم، مع الحفاظ على ترتيب الاقتراحات.
    users_by_id = {
        user.id: user
        for user in User.query.filter(User.id.in_(suggested_ids[:20])).all()
    }
    suggested_users = [
        users_by_id[user_id]
        for user_id in suggested_ids[:20]
        if user_id in users_by_id
    ]

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
        'followers_count': u.follower_count(),
        'is_following': current_user.is_following(u)
    } for u in users])
