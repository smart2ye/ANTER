import os
import uuid
import re
import subprocess
from flask import current_app, url_for
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from sqlalchemy import func

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def save_uploaded_image(file, subfolder=''):
    if not file or not hasattr(file, 'filename') or not file.filename:
        return ''
    if not allowed_file(file.filename):
        return ''
    ext = file.filename.rsplit('.', 1)[1].lower()
    new_name = str(uuid.uuid4()) + '.' + ext
    upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], subfolder)
    os.makedirs(upload_path, exist_ok=True)
    filepath = os.path.join(upload_path, new_name)
    file.save(filepath)
    try:
        from PIL import Image
        img = Image.open(filepath)
        img.thumbnail((800, 800))
        img.save(filepath, optimize=True, quality=85)
    except (ImportError, Exception):
        pass
    return os.path.join(subfolder, new_name) if subfolder else new_name

def parse_mentions(text):
    def replace_mention(match):
        username = match.group(1)
        return f'<a href="{url_for("users.profile", username=username)}" class="mention">@{username}</a>'
    pattern = r'@([\w.]+)'
    return re.sub(pattern, replace_mention, text)

ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'webm', 'avi', 'mov', 'mkv'}

def allowed_video_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_VIDEO_EXTENSIONS

def save_video_file(file, is_reel=False):
    if not file or not hasattr(file, 'filename') or not file.filename:
        return ''
    if not allowed_video_file(file.filename):
        return ''
    ext = file.filename.rsplit('.', 1)[1].lower()
    new_name = str(uuid.uuid4()) + '.' + ext
    subfolder = 'reels' if is_reel else 'videos'
    upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], subfolder)
    os.makedirs(upload_path, exist_ok=True)
    filepath = os.path.join(upload_path, new_name)
    file.save(filepath)
    return os.path.join(subfolder, new_name)

def create_thumbnail(video_path, is_reel=False):
    try:
        video_full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], video_path)
        thumb_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'thumbnails')
        os.makedirs(thumb_dir, exist_ok=True)
        thumb_name = str(uuid.uuid4()) + '.jpg'
        thumb_path = os.path.join(thumb_dir, thumb_name)
        cmd = ['ffmpeg', '-i', video_full_path, '-ss', '00:00:01', '-vframes', '1', '-q:v', '2', thumb_path]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        if os.path.exists(thumb_path):
            return os.path.join('thumbnails', thumb_name)
        return ''
    except Exception:
        return ''

# ============================================
# دوال الوسوم (Hashtags) - محسّنة
# ============================================

def extract_hashtags(text):
    """استخراج جميع الوسوم (#hashtag) من النص"""
    if not text:
        return []
    return re.findall(r'#([\w\u0600-\u06FF]+)', text)

def process_hashtags(post_id, content):
    """معالجة الوسوم مع التحديث الإحصائي"""
    from app.models import Hashtag, PostHashtag, HashtagStat
    from app.extensions import db
    
    if not content:
        return
    
    tags = extract_hashtags(content)
    for tag_name in tags:
        # البحث أو الإنشاء
        hashtag = Hashtag.query.filter_by(name=tag_name.lower()).first()
        if not hashtag:
            hashtag = Hashtag(name=tag_name.lower())
            db.session.add(hashtag)
            db.session.flush()
        
        # ربط المنشور بالوسم
        existing = PostHashtag.query.filter_by(post_id=post_id, hashtag_id=hashtag.id).first()
        if not existing:
            ph = PostHashtag(post_id=post_id, hashtag_id=hashtag.id)
            db.session.add(ph)
        
        # تحديث الإحصائيات
        hashtag.usage_count += 1
        hashtag.last_used = datetime.utcnow()
        
        # تسجيل الإحصائيات اليومية
        HashtagStat.record_usage(hashtag.id)
    
    db.session.commit()

def get_trending_hashtags(limit=10, hours=24):
    """احصل على الوسوم الرائجة"""
    from app.models import Hashtag, PostHashtag, Post
    from app.extensions import db
    
    since = datetime.utcnow() - timedelta(hours=hours)
    
    trending = db.session.query(
        Hashtag,
        func.count(PostHashtag.id).label('usage'),
        func.count(Post.id).label('posts')
    ).join(
        PostHashtag, Hashtag.id == PostHashtag.hashtag_id
    ).join(
        Post, Post.id == PostHashtag.post_id
    ).filter(
        Post.created_at >= since
    ).group_by(Hashtag.id).order_by(
        func.count(PostHashtag.id).desc()
    ).limit(limit).all()
    
    return trending

def search_hashtags(query, limit=10):
    """البحث عن وسوم"""
    from app.models import Hashtag
    
    if not query or len(query) < 1:
        return []
    
    return Hashtag.query.filter(
        Hashtag.name.contains(query.lower())
    ).order_by(
        Hashtag.usage_count.desc()
    ).limit(limit).all()

def format_hashtag_html(text):
    """تنسيق النص لعرض الوسوم كروابط"""
    def replace_hashtag(match):
        tag = match.group(1)
        return f'<a href="{url_for("hashtags.view", tag=tag)}" class="hashtag-link">#{tag}</a>'
    pattern = r'#([\w\u0600-\u06FF]+)'
    return re.sub(pattern, replace_hashtag, text)

# ============================================
# دوال تسجيل نشاط المستخدم
# ============================================
from flask import request
from user_agents import parse
import json

def log_user_activity(user_id, action, details=None):
    """تسجيل نشاط المستخدم في قاعدة البيانات"""
    from app.models import UserActivity
    from app.extensions import db
    
    user_agent_string = request.headers.get('User-Agent', '')
    ua = parse(user_agent_string) if user_agent_string else None
    
    activity = UserActivity(
        user_id=user_id,
        action=action,
        ip_address=request.remote_addr,
        user_agent=user_agent_string[:500],
        browser=f"{ua.browser.family} {ua.browser.version_string}" if ua and ua.browser else '',
        os=f"{ua.os.family} {ua.os.version_string}" if ua and ua.os else '',
        device_type=ua.device.family if ua else '',
        details=json.dumps(details) if details else None
    )
    db.session.add(activity)
    db.session.commit()
    return activity

def get_user_activity_summary(user_id, limit=50):
    """استرجاع آخر الأنشطة للمستخدم"""
    from app.models import UserActivity
    return UserActivity.query.filter_by(user_id=user_id).order_by(UserActivity.created_at.desc()).limit(limit).all()

# ============================================
# دوال حالة الاتصال
# ============================================

def get_user_status(user):
    """إرجاع حالة المستخدم (متصل / غير متصل)"""
    if not user or not user.last_seen:
        return {'status': 'offline', 'last_seen': 'منذ فترة'}
    
    now = datetime.utcnow()
    diff = now - user.last_seen
    
    if diff.total_seconds() < 300:  # 5 دقائق
        return {'status': 'online', 'last_seen': 'متصل الآن'}
    elif diff.total_seconds() < 3600:  # أقل من ساعة
        minutes = int(diff.total_seconds() / 60)
        return {'status': 'offline', 'last_seen': f'منذ {minutes} دقيقة'}
    elif diff.total_seconds() < 86400:  # أقل من يوم
        hours = int(diff.total_seconds() / 3600)
        return {'status': 'offline', 'last_seen': f'منذ {hours} ساعة'}
    else:
        days = int(diff.total_seconds() / 86400)
        return {'status': 'offline', 'last_seen': f'منذ {days} يوم'}

def get_status_icon(user):
    """إرجاع أيقونة الحالة مع اللون (HTML)"""
    status = get_user_status(user)
    if status['status'] == 'online':
        return f'<span class="status-indicator online"><span class="status-dot"></span> 🟢 متصل الآن</span>'
    else:
        return f'<span class="status-indicator offline"><span class="status-dot"></span> 🔴 {status["last_seen"]}</span>'
