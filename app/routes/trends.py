from flask import Blueprint, render_template, jsonify
from flask_login import login_required
from app.models import Post
from sqlalchemy import func, desc
from datetime import datetime, timedelta

trends_bp = Blueprint('trends', __name__, url_prefix='/trends')

@trends_bp.route('/')
@login_required
def index():
    # المنشورات الأكثر تفاعلاً خلال آخر 24 ساعة
    last_24h = datetime.utcnow() - timedelta(hours=24)
    trending_posts = Post.query.filter(
        Post.created_at > last_24h
    ).outerjoin(Post.likes).outerjoin(Post.comments)\
     .group_by(Post.id)\
     .order_by(
         (func.count(Post.likes) * 2 + func.count(Post.comments) * 3).desc(),
         Post.created_at.desc()
     ).limit(20).all()
    
    return render_template('trends/index.html', posts=trending_posts)
