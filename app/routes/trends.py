from flask import Blueprint, render_template, jsonify
from flask_login import login_required
from app.models import Post, Hashtag, Like, Comment, Repost
from app.extensions import db
from sqlalchemy import func, desc
from sqlalchemy.orm import defer
from datetime import datetime, timedelta
import math

trends_bp = Blueprint('trends', __name__, url_prefix='/trends')

def calculate_hot_score(likes_count, comments_count, reposts_count, created_at):
    """خوارزمية حساب قوة المنشور (Hot Score) بناءً على التفاعل والزمن"""
    # الأوزان: الإعجاب (1)، التعليق (3)، المشاركة (5)
    engagement = (likes_count * 1) + (comments_count * 3) + (reposts_count * 5)
    
    # حساب فرق الوقت بالساعات
    time_diff = (datetime.utcnow() - created_at).total_seconds() / 3600
    
    # خوارزمية التلاشي الزمني (Time Decay)
    # Score = Engagement / (Time + 2)^1.5
    score = engagement / math.pow((time_diff + 2), 1.5)
    return score

@trends_bp.route('/')
@login_required
def index():
    # 1. حساب التريندات للمنشورات (آخر 48 ساعة)
    last_48h = datetime.utcnow() - timedelta(hours=48)
    
    # جلب المنشورات مع عدد التفاعلات
    posts = Post.query.options(defer(Post.image_data)).filter(Post.created_at > last_48h).order_by(Post.id.desc()).limit(300).all()
    
    scored_posts = []
    for post in posts:
        l_count = post.likes.count()
        c_count = post.comments.count()
        
        # محاولة جلب عدد المشاركات إذا كان الموديل موجوداً
        r_count = 0
        try:
            r_count = Repost.query.filter_by(post_id=post.id).count()
        except:
            pass
            
        score = calculate_hot_score(l_count, c_count, r_count, post.created_at)
        scored_posts.append((post, score))
    
    # ترتيب المنشورات حسب السكور
    trending_posts = [p[0] for p in sorted(scored_posts, key=lambda x: x[1], reverse=True)[:20]]
    
    # 2. حساب الهاشتاقات الأكثر تداولاً (Smart Hashtag Trends)
    hashtag_scores = {}
    for post, score in scored_posts:
        try:
            # التحقق من وجود علاقة hashtags
            for tag in post.hashtags:
                tag_name = tag.name
                hashtag_scores[tag_name] = hashtag_scores.get(tag_name, 0) + score
        except:
            # إذا لم تكن العلاقة موجودة، نحاول استخراجها من النص كحل بديل
            from app.utils.helpers import extract_hashtags
            tags = extract_hashtags(post.content)
            for tag_name in tags:
                name = tag_name.lower().replace('#', '')
                hashtag_scores[name] = hashtag_scores.get(name, 0) + score
            
    trending_hashtags = sorted(hashtag_scores.items(), key=lambda x: x[1], reverse=True)[:10]
    
    return render_template('trends/index.html', 
                           posts=trending_posts, 
                           trending_hashtags=trending_hashtags)
