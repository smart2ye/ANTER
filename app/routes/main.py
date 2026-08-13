from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app.models import Post, Video, Like, Comment, Follow, HiddenPost
from app.extensions import db
from sqlalchemy import func, or_, and_
from datetime import datetime, timedelta
import math
import re
from collections import Counter
import os

main_bp = Blueprint('main', __name__)

STOP_WORDS = {'ال', 'و', 'في', 'من', 'على', 'إلى', 'عن', 'مع', 'بين', 'كل', 'بعض', 'هذا', 'هذه', 'ذلك', 'تلك', 'كان', 'كانت', 'يكون', 'تصبح', 'أصبح', 'يصبح', 'ما', 'لا', 'هل', 'أم', 'أو', 'ثم', 'حتى', 'لكن', 'لأن', 'حيث', 'بينما', 'عندما', 'إذا', 'إن', 'أن', 'قد', 'سوف', 'سيكون', 'لم', 'لن', 'ليس', 'ليست'}

def extract_keywords(text):
    if not text:
        return []
    text = re.sub(r'[^\w\s]', ' ', text)
    words = text.split()
    keywords = [w for w in words if len(w) > 2 and w not in STOP_WORDS]
    return keywords

def get_user_interests(user_id):
    interests = []
    try:
        liked_posts = db.session.query(Post.content).join(Like, Like.post_id == Post.id)\
            .filter(Like.user_id == user_id).limit(30).all()
        for post in liked_posts:
            interests.extend(extract_keywords(post.content))
        comments = Comment.query.filter_by(author_id=user_id).limit(30).all()
        for comment in comments:
            interests.extend(extract_keywords(comment.content))
        own_posts = Post.query.filter_by(author_id=user_id).limit(20).all()
        for post in own_posts:
            interests.extend(extract_keywords(post.content))
    except Exception:
        return []
    if interests:
        counter = Counter(interests)
        return [word for word, count in counter.most_common(20)]
    return []

def calculate_similarity(text, interests):
    if not interests:
        return 0
    keywords = extract_keywords(text)
    if not keywords:
        return 0
    matches = sum(1 for k in keywords if k in interests)
    return matches / len(interests) if interests else 0

def get_post_engagement_score(post):
    return post.like_count() * 2 + post.comment_count() * 3

@main_bp.route('/')
@login_required
def index():
    following_ids = [f.followed_id for f in current_user.following] + [current_user.id]
    interests = get_user_interests(current_user.id)
    followed_posts = Post.query.filter(Post.author_id.in_(following_ids)).all()
    suggested_posts = Post.query.filter(
        ~Post.author_id.in_(following_ids),
        Post.created_at > datetime.utcnow() - timedelta(days=7)
    ).all()
    suggested_with_scores = []
    for post in suggested_posts:
        similarity = calculate_similarity(post.content, interests)
        engagement = get_post_engagement_score(post)
        score = similarity * 3 + (engagement / 10)
        suggested_with_scores.append((post, score))
    suggested_with_scores.sort(key=lambda x: x[1], reverse=True)
    top_suggested = [post for post, score in suggested_with_scores[:10]]
    if followed_posts or top_suggested:
        all_posts = followed_posts + top_suggested
    else:
        all_posts = Post.query.order_by(Post.created_at.desc()).limit(20).all()
    hidden_ids = [h.post_id for h in HiddenPost.query.filter_by(user_id=current_user.id).all()]
    if hidden_ids:
        all_posts = [p for p in all_posts if p.id not in hidden_ids]
    def sort_key(post):
        is_suggested = post in top_suggested
        time_weight = (datetime.utcnow() - post.created_at).total_seconds() / 3600
        return (1.5 if not is_suggested else 1) * (-time_weight)
    all_posts.sort(key=sort_key)
    return render_template('index.html', posts=all_posts, suggested_posts=top_suggested)

@main_bp.route('/api/posts')
@login_required
def api_posts():
    page = request.args.get('page', 1, type=int)
    per_page = 5
    following_ids = [f.followed_id for f in current_user.following] + [current_user.id]
    interests = get_user_interests(current_user.id)
    followed_posts = Post.query.filter(Post.author_id.in_(following_ids)).all()
    suggested_posts = Post.query.filter(
        ~Post.author_id.in_(following_ids),
        Post.created_at > datetime.utcnow() - timedelta(days=7)
    ).all()
    suggested_with_scores = []
    for post in suggested_posts:
        similarity = calculate_similarity(post.content, interests)
        engagement = get_post_engagement_score(post)
        score = similarity * 3 + (engagement / 10)
        suggested_with_scores.append((post, score))
    suggested_with_scores.sort(key=lambda x: x[1], reverse=True)
    top_suggested = [post for post, score in suggested_with_scores[:10]]
    if followed_posts or top_suggested:
        all_posts = followed_posts + top_suggested
    else:
        all_posts = Post.query.order_by(Post.created_at.desc()).limit(20).all()
    hidden_ids = [h.post_id for h in HiddenPost.query.filter_by(user_id=current_user.id).all()]
    if hidden_ids:
        all_posts = [p for p in all_posts if p.id not in hidden_ids]
    def sort_key(post):
        is_suggested = post in top_suggested
        time_weight = (datetime.utcnow() - post.created_at).total_seconds() / 3600
        return (1.5 if not is_suggested else 1) * (-time_weight)
    all_posts.sort(key=sort_key)
    start = (page - 1) * per_page
    end = start + per_page
    paginated_posts = all_posts[start:end]
    has_next = len(all_posts) > end
    data = []
    for post in paginated_posts:
        data.append({
            'id': post.id,
            'content': post.content,
            'image': post.image,
            'created_at': post.created_at.strftime('%Y-%m-%d %H:%M'),
            'author': {
                'id': post.author.id,
                'name': post.author.name,
                'username': post.author.username,
                'avatar': post.author.avatar
            },
            'like_count': post.like_count(),
            'comment_count': post.comment_count(),
            'is_author': post.author_id == current_user.id,
            'is_suggested': post in top_suggested,
            'html': render_template('_post_card.html', post=post)
        })
    return jsonify({'posts': data, 'has_next': has_next})

@main_bp.route('/reels')
@login_required
def reels_feed():
    videos = Video.query.filter_by(is_reel=True).order_by(Video.created_at.desc()).all()
    return render_template('main_reels.html', videos=videos)

@main_bp.route('/privacy')
def privacy():
    return render_template('privacy.html')

@main_bp.route('/terms')
def terms():
    return render_template('terms.html')

@main_bp.route('/about')
def about():
    return render_template('about.html')

@main_bp.route('/sitemap.xml')
def sitemap():
    from app.models import User, Post
    pages = [
        {'loc': url_for('main.index', _external=True), 'priority': 1.0},
        {'loc': url_for('main.about', _external=True), 'priority': 0.8},
        {'loc': url_for('main.privacy', _external=True), 'priority': 0.5},
        {'loc': url_for('main.terms', _external=True), 'priority': 0.5},
        {'loc': url_for('auth.login', _external=True), 'priority': 0.6},
        {'loc': url_for('auth.register', _external=True), 'priority': 0.7},
        {'loc': url_for('explore.explore', _external=True), 'priority': 0.9},
        {'loc': url_for('videos.reels', _external=True), 'priority': 0.8},
    ]
    users = User.query.limit(100).all()
    for user in users:
        pages.append({
            'loc': url_for('users.profile', username=user.username, _external=True),
            'priority': 0.8,
            'lastmod': user.created_at.strftime('%Y-%m-%d') if user.created_at else datetime.now().strftime('%Y-%m-%d')
        })
    posts = Post.query.limit(500).all()
    for post in posts:
        pages.append({
            'loc': url_for('posts.view_post', post_id=post.id, _external=True),
            'priority': 0.9,
            'lastmod': post.created_at.strftime('%Y-%m-%d') if post.created_at else datetime.now().strftime('%Y-%m-%d')
        })
    sitemap_xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for page in pages:
        sitemap_xml += '  <url>\n'
        sitemap_xml += f'    <loc>{page["loc"]}</loc>\n'
        if 'lastmod' in page:
            sitemap_xml += f'    <lastmod>{page["lastmod"]}</lastmod>\n'
        if 'priority' in page:
            sitemap_xml += f'    <priority>{page["priority"]:.1f}</priority>\n'
        sitemap_xml += '  </url>\n'
    sitemap_xml += '</urlset>'
    return sitemap_xml, 200, {'Content-Type': 'application/xml'}

@main_bp.route('/update_interests', methods=['POST'])
@login_required
def update_interests():
    return jsonify({'success': True, 'message': 'تم تحديث الاهتمامات'})

# ============================================
# ملف التحقق من Google (أبسط حل)
# ============================================
@main_bp.route('/google-site-verification-7Uaxo4sE9avUI6VqAsGp-ldxoslHE10dRIa2Q-Skak0.html')
def google_verification():
    return "google-site-verification=7Uaxo4sE9avUI6VqAsGp-ldxoslHE10dRIa2Q-Skak0"

@main_bp.route('/api/users')
@login_required
def api_users():
    """عرض جميع المستخدمين (للمشرفين فقط)"""
    if not current_user.is_admin:
        return jsonify({'error': 'غير مصرح'}), 403
    
    users = User.query.order_by(User.created_at.desc()).all()
    return jsonify([{
        'id': u.id,
        'username': u.username,
        'name': u.name,
        'email': u.email,
        'created_at': u.created_at.isoformat() if u.created_at else None,
        'is_verified': u.is_verified,
        'is_admin': u.is_admin
    } for u in users])
