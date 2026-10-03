import os
import uuid
import re
import subprocess
import socket
import ipaddress
from urllib.parse import urljoin, urlparse

from flask import current_app, url_for


def _is_safe_preview_url(value):
    """Allow only public HTTP(S) hosts for server-side link previews."""
    try:
        parsed = urlparse(value)
        if parsed.scheme not in {'http', 'https'} or not parsed.hostname:
            return False
        if parsed.username or parsed.password:
            return False
        host = parsed.hostname.rstrip('.').lower()
        if host in {'localhost', 'localhost.localdomain'} or host.endswith('.local'):
            return False
        for result in socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == 'https' else 80), type=socket.SOCK_STREAM):
            address = ipaddress.ip_address(result[4][0])
            if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved or address.is_multicast or address.is_unspecified:
                return False
        return True
    except (ValueError, OSError, socket.gaierror):
        return False


def extract_link_metadata(text):
    """Extract safe Open Graph metadata from the first public URL in post text."""
    if not text:
        return None, None, None, None

    urls = re.findall(r'https?://[^\s<>\"]+|www\.[^\s<>\"]+', text)
    if not urls:
        return None, None, None, None

    target_url = urls[0]
    if target_url.startswith('www.'):
        target_url = 'https://' + target_url
    if not _is_safe_preview_url(target_url):
        return None, None, None, None

    try:
        import requests
        from bs4 import BeautifulSoup

        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; ANTER-LinkPreview/1.0)',
            'Accept': 'text/html,application/xhtml+xml',
        }
        session = requests.Session()
        current_url = target_url
        response = None
        for _ in range(3):
            response = session.get(
                current_url,
                headers=headers,
                timeout=(2, 3),
                allow_redirects=False,
                stream=True,
            )
            if response.is_redirect or response.is_permanent_redirect:
                next_url = urljoin(current_url, response.headers.get('Location', ''))
                response.close()
                if not _is_safe_preview_url(next_url):
                    return None, None, None, None
                current_url = next_url
                continue
            break

        if response is None or response.status_code != 200:
            if response is not None:
                response.close()
            return None, None, None, None

        content_type = response.headers.get('Content-Type', '').lower()
        if content_type and 'html' not in content_type and 'xhtml' not in content_type:
            response.close()
            return current_url, urlparse(current_url).netloc, None, None

        body = b''
        for chunk in response.iter_content(chunk_size=16384):
            body += chunk
            if len(body) >= 1024 * 1024:
                break
        response.close()

        soup = BeautifulSoup(body, 'html.parser')

        def meta_content(*selectors):
            for selector in selectors:
                tag = soup.find('meta', **selector)
                if tag and tag.get('content'):
                    return tag['content'].strip()
            return None

        title = meta_content({'property': 'og:title'}, {'name': 'twitter:title'})
        if not title and soup.title and soup.title.string:
            title = soup.title.string.strip()

        description = meta_content(
            {'property': 'og:description'},
            {'name': 'description'},
            {'name': 'twitter:description'},
        )
        image = meta_content({'property': 'og:image'}, {'name': 'twitter:image'})
        if image:
            image = urljoin(current_url, image)
            if not _is_safe_preview_url(image):
                image = None

        domain = urlparse(current_url).netloc
        return current_url, title or domain, description, image
    except Exception:
        return target_url, urlparse(target_url).netloc, None, None

from werkzeug.utils import secure_filename

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


def allowed_audio_file(filename):
    return (
        bool(filename)
        and '.' in filename
        and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_AUDIO_EXTENSIONS']
    )


def save_audio_file(file):
    """حفظ رسالة صوتية مرفوعة وإرجاع مسارها النسبي."""
    if not file or not hasattr(file, 'filename') or not file.filename:
        return ''
    if not allowed_audio_file(file.filename):
        return ''

    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f'{uuid.uuid4()}.{ext}'
    upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'audio')
    os.makedirs(upload_path, exist_ok=True)
    file.save(os.path.join(upload_path, filename))
    return os.path.join('audio', filename)


def parse_mentions(text):
    from app.models import User
    def replace_mention(match):
        username = match.group(1)
        user = User.query.filter_by(username=username).first()
        if user:
            return f'<a href="{url_for("users.profile", username=username)}" class="mention">@{username}</a>'
        return f'@{username}'
    # دعم الحروف العربية في الـ Regex للإشارات
    pattern = r'@([\w\u0600-\u06FF.]+)'
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
# دوال الوسوم (Hashtags)
# ============================================

def extract_hashtags(text):
    """استخراج جميع الوسوم (#hashtag) من النص"""
    import re
    return re.findall(r'(?<!&)#([\w\u0600-\u06FF]+)', text)

def process_hashtags(post_id, content):
    """معالجة الوسوم في المنشور (إنشاء وربط)"""
    from app.models import Hashtag, PostHashtag
    from app.extensions import db
    
    if not content:
        return
    
    tags = extract_hashtags(content)
    for tag_name in tags:
        # بحث أو إنشاء الوسم
        hashtag = Hashtag.query.filter_by(name=tag_name.lower()).first()
        if not hashtag:
            hashtag = Hashtag(name=tag_name.lower())
            db.session.add(hashtag)
            db.session.flush()
        # ربط المنشور بالوسم (إذا لم يكن موجوداً)
        existing = PostHashtag.query.filter_by(post_id=post_id, hashtag_id=hashtag.id).first()
        if not existing:
            ph = PostHashtag(post_id=post_id, hashtag_id=hashtag.id)
            db.session.add(ph)
    db.session.commit()

# ============================================
# دوال تسجيل نشاط المستخدم
# ============================================
from flask import request
from user_agents import parse
import json

_ACTIVITY_SENSITIVE_KEYS = {
    'password', 'password_hash', 'current_password', 'new_password',
    'email', 'phone', 'token', 'api_key', 'secret', 'content', 'bio',
}
_ACTIVITY_ALLOWED_DETAIL_KEYS = {
    'fields', 'target_username', 'post_id', 'comment_id', 'video_id',
    'story_id', 'reaction', 'scope', 'attachment',
}


def _safe_activity_details(details):
    """يخزن وصفاً تشغيلياً محدوداً من دون كلمات مرور أو قيم الاتصال الشخصية."""
    if not isinstance(details, dict):
        return None
    safe = {}
    for key, value in details.items():
        normalized_key = str(key).strip().lower()
        if normalized_key in _ACTIVITY_SENSITIVE_KEYS or normalized_key not in _ACTIVITY_ALLOWED_DETAIL_KEYS:
            continue
        if normalized_key == 'fields':
            if isinstance(value, (list, tuple)):
                safe[normalized_key] = [str(item)[:40] for item in value[:12]]
            continue
        if isinstance(value, (str, int, float, bool)):
            safe[normalized_key] = str(value)[:120]
    return safe or None


def log_user_activity(user_id, action, details=None, *, commit=True):
    """يسجل نشاطاً خاصاً بصاحبه فقط، مع إخفاء القيم الحساسة من التفاصيل."""
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
        details=json.dumps(_safe_activity_details(details), ensure_ascii=False) if _safe_activity_details(details) else None,
    )
    db.session.add(activity)
    if commit:
        db.session.commit()
    else:
        db.session.flush()
    return activity


def get_user_activity_summary(user_id, limit=50):
    """يسترجع أحدث الأنشطة لصاحب الحساب فقط."""
    from app.models import UserActivity
    return UserActivity.query.filter_by(user_id=user_id).order_by(UserActivity.created_at.desc()).limit(limit).all()

# ============================================
# دوال حالة الاتصال
# ============================================
from datetime import datetime, timedelta

def get_user_status(user, viewer=None):
    """إرجاع حالة المستخدم (متصل / غير متصل)."""
    from flask import current_app

    assistant_username = current_app.config.get('ANTER_ASSISTANT_USERNAME', 'anter_assistant')
    if user and user.username == assistant_username:
        return {'status': 'online', 'last_seen': 'متصل الآن'}
    if not user:
        return {'status': 'offline', 'last_seen': 'منذ فترة'}
    can_view_presence = (
        getattr(user, 'show_online_status', True)
        or (viewer and (viewer.id == user.id or getattr(viewer, 'is_admin', False)))
    )
    if not can_view_presence:
        return {'status': 'hidden', 'last_seen': 'الحالة مخفية'}
    if not user.last_seen:
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

def get_status_icon(user, viewer=None):
    """إرجاع أيقونة الحالة مع اللون (HTML)"""
    status = get_user_status(user, viewer)
    if status['status'] == 'online':
        return f'<span class="status-indicator online"><span class="status-dot"></span> 🟢 متصل الآن</span>'
    else:
        return f'<span class="status-indicator offline"><span class="status-dot"></span> 🔴 {status["last_seen"]}</span>'

# ============================================================
# ANTER: عرض المحتوى الغني — كتل كود + hashtags + mentions
# ============================================================
_CODE_BLOCK_RE = re.compile(
    r'```([a-zA-Z0-9_+\-]{0,32})[ \t]*\r?\n(.*?)```',
    re.DOTALL,
)


def _render_plain_segment(text):
    """يطبّق hashtags و mentions على نص مُهرَّب من HTML."""
    from markupsafe import escape
    from app.models import User

    escaped = str(escape(text))

    def replace_mention(match):
        username = match.group(1)
        user = User.query.filter_by(username=username).first()
        if user:
            return (
                f'<a href="{url_for("users.profile", username=username)}" '
                f'class="mention">@{escape(username)}</a>'
            )
        return f'@{escape(username)}'

    escaped = re.sub(r'@([\w\u0600-\u06FF.]+)', replace_mention, escaped)

    def replace_tag(match):
        tag = match.group(1)
        tag_url = url_for('explore.hashtag', tag=tag)
        return f'<a href="{escape(tag_url)}" class="hashtag-link">#{escape(tag)}</a>'

    escaped = re.sub(r'(?<!&)#([\w\u0600-\u06FF]+)', replace_tag, escaped)

    return escaped


def render_rich_text(content):
    """يحوّل محتوى المستخدم إلى HTML آمن مع دعم كتل الكود.

    - ```lang\n...\n``` → <pre><code class="language-lang">
    - #hashtag → رابط
    - @mention → رابط
    - بقية المحتوى: يُهرَّب من HTML (XSS-safe)
    """
    from markupsafe import Markup, escape
    from html import unescape

    if not content:
        return Markup('')

    text = unescape(str(content))

    matches = list(_CODE_BLOCK_RE.finditer(text))
    if not matches:
        return Markup(_render_plain_segment(text))

    out = []
    cursor = 0
    for m in matches:
        if m.start() > cursor:
            out.append(_render_plain_segment(text[cursor:m.start()]))
        lang = (m.group(1) or '').strip().lower()[:32]
        code = m.group(2).rstrip('\n')
        lang_class = f' class="language-{escape(lang)}"' if lang else ''
        lang_label = escape(lang or 'code')
        out.append(
            '<div class="anter-codeblock">'
            '<div class="anter-codeblock__head">'
            f'<span class="anter-codeblock__lang">{lang_label}</span>'
            '<button type="button" class="anter-codeblock__copy" data-anter-code-copy>'
            '<i class="far fa-copy" aria-hidden="true"></i> <span>نسخ</span>'
            '</button>'
            '</div>'
            f'<pre><code{lang_class}>{escape(code)}</code></pre>'
            '</div>'
        )
        cursor = m.end()
    if cursor < len(text):
        out.append(_render_plain_segment(text[cursor:]))

    return Markup(''.join(out))

