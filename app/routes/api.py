from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from app.models import Post, User, Video
from app.extensions import db

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/posts')
@login_required
def get_posts():
    """جلب آخر المنشورات (JSON)"""
    posts = Post.query.order_by(Post.created_at.desc()).limit(20).all()
    return jsonify([{
        'id': p.id,
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
    } for p in posts])

@api_bp.route('/users/<username>')
@login_required
def get_user(username):
    """جلب معلومات مستخدم (JSON)"""
    user = User.query.filter_by(username=username).first_or_404()
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
    """جلب الريلزات (JSON)"""
    videos = Video.query.filter_by(is_reel=True).order_by(Video.created_at.desc()).limit(20).all()
    return jsonify([{
        'id': v.id,
        'title': v.title,
        'description': v.description,
        'thumbnail': v.thumbnail_path,
        'views': v.views,
        'likes': v.like_count(),
        'comments': v.comment_count(),
        'author': {
            'id': v.author.id,
            'username': v.author.username,
            'name': v.author.name
        }
    } for v in videos])
