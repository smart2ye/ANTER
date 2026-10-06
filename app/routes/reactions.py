from flask import Blueprint, request, url_for
from flask_login import login_required
from app.extensions import db
from app.models import Post, User, Like

reactions_bp = Blueprint('reactions', __name__)

@reactions_bp.route('/post/<int:post_id>/reactions.json')
@login_required
def post_reactions_json(post_id):
    """يُرجع قائمة المتفاعلين وإحصائياتهم بصيغة JSON — لعرضها في نافذة منبثقة."""
    from flask import jsonify
    from flask_login import current_user

    post = Post.query.get_or_404(post_id)
    reaction_type = request.args.get('type')

    query = (
        db.session.query(User, Like.reaction_type)
        .join(Like, Like.user_id == User.id)
        .filter(
            Like.post_id == post_id,
            User.is_deleted.is_(False),
        )
    )
    if reaction_type and reaction_type in ['like', 'love', 'haha', 'angry', 'sad']:
        query = query.filter(Like.reaction_type == reaction_type)

    # نرتب حسب تاريخ التفاعل (الأحدث أولًا)
    rows = query.order_by(Like.id.desc()).all()

    users_payload = []
    for user, rtype in rows:
        users_payload.append({
            'id': user.id,
            'username': user.username,
            'name': user.name or user.username,
            'avatar': url_for('media.avatar', user_id=user.id) if user.avatar_data else url_for('static', filename=(user.avatar or 'img/default_avatar_male.png')),
            'reaction': rtype,
            'is_me': (current_user.is_authenticated and current_user.id == user.id),
            'is_verified': bool(getattr(user, 'is_verified', False)),
        })

    stats = {}
    for rt in ['like', 'love', 'haha', 'angry', 'sad']:
        stats[rt] = (
            db.session.query(Like)
            .join(User, User.id == Like.user_id)
            .filter(
                Like.post_id == post_id,
                Like.reaction_type == rt,
                User.is_deleted.is_(False),
            )
            .count()
        )

    return jsonify({
        'success': True,
        'post_id': post.id,
        'total': len(users_payload),
        'stats': stats,
        'reaction_filter': reaction_type or None,
        'users': users_payload,
    })

