from flask import Blueprint, render_template, request, jsonify, abort
from flask_login import login_required, current_user
from app.models import Hashtag, Post, PostHashtag, User
from app.extensions import db
from app.utils.helpers import get_trending_hashtags, search_hashtags
from sqlalchemy import func
from datetime import datetime, timedelta

hashtags_bp = Blueprint('hashtags', __name__, url_prefix='/hashtags')

@hashtags_bp.route('/')
@login_required
def index():
    """صفحة الوسوم الرائجة"""
    page = request.args.get('page', 1, type=int)
    trending = get_trending_hashtags(limit=50)
    
    return render_template('hashtags/index.html', trending=trending)

@hashtags_bp.route('/<tag>')
@login_required
def view(tag):
    """عرض وسم معين ومنشوراته"""
    hashtag = Hashtag.query.filter_by(name=tag.lower()).first_or_404()
    
    # احصل على المنشورات المرتبطة بهذا الوسم
    page = request.args.get('page', 1, type=int)
    posts_query = db.session.query(Post).join(
        PostHashtag, Post.id == PostHashtag.post_id
    ).filter(
        PostHashtag.hashtag_id == hashtag.id
    ).order_by(Post.created_at.desc())
    
    posts = posts_query.paginate(page=page, per_page=20)
    
    # احسب الإحصائيات
    stats = hashtag.get_trending_score(hours=24)
    
    return render_template('hashtags/view.html', 
        hashtag=hashtag, 
        posts=posts, 
        stats=stats
    )

@hashtags_bp.route('/api/search')
@login_required
def api_search():
    """API للبحث عن وسوم (Autocomplete)"""
    q = request.args.get('q', '', type=str).strip()
    
    if not q or len(q) < 1:
        return jsonify([])
    
    hashtags = search_hashtags(q, limit=10)
    
    return jsonify([{
        'name': h.name,
        'usage': h.usage_count,
        'posts': h.post_count()
    } for h in hashtags])

@hashtags_bp.route('/api/trending')
@login_required
def api_trending():
    """API لاسترجاع الوسوم الرائجة (JSON)"""
    limit = request.args.get('limit', 10, type=int)
    hours = request.args.get('hours', 24, type=int)
    
    trending = get_trending_hashtags(limit=limit, hours=hours)
    
    return jsonify([{
        'name': h[0].name,
        'usage': h[1],
        'posts': h[2],
        'url': f'/hashtags/{h[0].name}'
    } for h in trending])

@hashtags_bp.route('/api/stats/<tag>')
@login_required
def api_stats(tag):
    """احصائيات الوسم (JSON)"""
    hashtag = Hashtag.query.filter_by(name=tag.lower()).first_or_404()
    
    stats_24h = hashtag.get_trending_score(hours=24)
    stats_7d = hashtag.get_trending_score(hours=168)
    stats_30d = hashtag.get_trending_score(hours=720)
    
    return jsonify({
        'name': hashtag.name,
        'usage_total': hashtag.usage_count,
        'posts_total': hashtag.post_count(),
        'last_used': hashtag.last_used.isoformat() if hashtag.last_used else None,
        'stats_24h': stats_24h,
        'stats_7d': stats_7d,
        'stats_30d': stats_30d
    })
