import time
from flask import Flask, flash, redirect, request, session, url_for
from werkzeug.exceptions import RequestEntityTooLarge
from app.config import Config
from app.extensions import db, login_manager, csrf
from app.models import (
    User,
    CallSignal,
    CallLog,
    MobileAccessToken,
    MobileBrowserAuthorization,
    MutedConversation,
    UserBlock,
)
from app.routes import register_blueprints
import os
import secrets
from datetime import datetime, timedelta
from html import unescape


def _get_admin_path(config):
    """Return an explicit route or a fresh random route for this app startup."""
    configured_path = os.environ.get("ADMIN_PATH", "").strip().strip("/")
    if configured_path:
        return configured_path
    return f"admin-{secrets.token_urlsafe(24)}"


def create_app(test_config=None):
    app = Flask(__name__)

    # تفعيل ضغط gzip/brotli لكل الردود (CSS من 185 KB → ~30 KB)
    try:
        from flask_compress import Compress
        Compress(app)
    except Exception:
        pass
    app.config.from_object(Config)

    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # يتغير المسار العشوائي عند كل تشغيل ولا يُطبع في السجلات.
    # يمكن تثبيته صراحةً عبر متغير البيئة ADMIN_PATH عند الحاجة التشغيلية.
    app.config["ADMIN_PATH"] = _get_admin_path(app.config)

    register_blueprints(app)
    
    from app.routes.stories import stories_bp

    @app.errorhandler(RequestEntityTooLarge)
    def handle_request_too_large(error):
        if request.path.startswith('/videos/upload'):
            max_video_mb = app.config['MAX_VIDEO_UPLOAD_BYTES'] // (1024 * 1024)
            flash(f'تعذر رفع الفيديو لأن حجمه أكبر من الحد المسموح ({max_video_mb} MB).', 'danger')
            return redirect(url_for('videos.upload'))
        return 'حجم الطلب أكبر من الحد المسموح.', 413

    with app.app_context():
        from app.services.startup_maintenance import run_startup_schema_upgrades
        schema_was_upgraded = run_startup_schema_upgrades(app)
        from app.services.anter_assistant import (
            ensure_anter_assistant_followed_by_all_users,
            ensure_anter_assistant_user,
        )
        from app.services.owner_admin import ensure_configured_owner_is_admin
        ensure_anter_assistant_user()
        # متابعة الحسابات القائمة للمساعد ترقية لمرة واحدة وليست عملاً لكل إيقاظ.
        if schema_was_upgraded:
            ensure_anter_assistant_followed_by_all_users()
        ensure_configured_owner_is_admin()
        db.session.commit()

        # ============================================
    # دالة عامة لحساب التفاعلات

    # ============================================
    from sqlalchemy import func

    def get_reaction_counts(post_id):
        from app.models import Like
        counts = db.session.query(
            Like.reaction_type,
            func.count(Like.id).label('count')
        ).filter(Like.post_id == post_id).group_by(Like.reaction_type).all()
        result = {'like': 0, 'love': 0, 'haha': 0, 'angry': 0, 'sad': 0}
        for c in counts:
            result[c.reaction_type] = c.count
        return result

    app.add_template_global(get_reaction_counts, name='get_reaction_counts')
    
    # ============================================
    # آخر المتفاعلين بالمنشور
    # ============================================
    def get_recent_reaction_users(post_id, limit=3):
        from app.models import Like, User
        from flask_login import current_user

        if not getattr(current_user, 'is_authenticated', False):
            return []

        reactions = (
            Like.query
            .filter_by(post_id=post_id)
            .order_by(Like.created_at.desc(), Like.id.desc())
            .all()
        )

        current_reaction = next(
            (item for item in reactions if item.user_id == current_user.id),
            None
        )

        selected = []

        if current_reaction:
            selected.append(current_reaction)

        for item in reactions:
            if len(selected) >= limit:
                break
            if item.user_id == current_user.id:
                continue
            selected.append(item)

        users = []
        seen = set()

        for item in selected:
            if item.user_id in seen:
                continue

            user = User.query.get(item.user_id)
            if not user:
                continue
            # ANTER: لا نُظهر المتفاعلين المحذوفين.
            if getattr(user, 'is_deleted', False):
                continue

            seen.add(item.user_id)

            users.append({
                'id': user.id,
                'name': user.name or user.username or 'مستخدم',
                'is_current_user': user.id == current_user.id
            })

        return users

    app.add_template_global(
        get_recent_reaction_users,
        name='get_recent_reaction_users'
    )


    # ============================================
    # جعل get_status_icon متاحة في جميع القوالب
    # ============================================
    from app.utils.helpers import get_status_icon
    from app.utils.media_urls import avatar_url, post_image_url
    app.add_template_global(get_status_icon, name='get_status_icon')
    app.add_template_global(avatar_url, name='avatar_url')
    app.add_template_global(post_image_url, name='post_image_url')

    @app.context_processor
    def inject_admin_pending_count():
        from flask_login import current_user
        from flask import request
        if not current_user.is_authenticated or not getattr(current_user, 'is_admin', False):
            return {'admin_pending_requests': 0}
        if not request.path.startswith('/admin'):
            return {'admin_pending_requests': 0}
        try:
            from app.extensions import db
            from app.models import Report
            from app.routes.admin import ACCOUNT_REQUEST_REASONS
            count = db.session.query(Report).filter(
                Report.reason.in_(ACCOUNT_REQUEST_REASONS),
                Report.status == 'pending',
            ).count()
            return {'admin_pending_requests': count}
        except Exception:
            return {'admin_pending_requests': 0}

    @app.context_processor
    def inject_assistant_account_switching():
        from flask_login import current_user
        from app.services.anter_account_switching import can_switch_back, can_switch_to_assistant

        switch_owner_id = session.get('anter_assistant_switch_owner_id')
        return {
            'can_switch_to_anter_assistant': can_switch_to_assistant(current_user),
            'can_switch_back_to_owner': can_switch_back(current_user, switch_owner_id),
        }

    # تحويل الوسوم في المحتوى النصي إلى روابط لصفحات الوسوم، مع إبقاء النص آمناً.
    from flask import url_for
    from markupsafe import Markup, escape
    import re

    def verified_badge(user):
        """شارة ثابتة وآمنة تظهر فقط للحسابات الموثقة فعلياً."""
        if not getattr(user, 'is_verified', False):
            return Markup('')
        return Markup(
            '<i class="fas fa-check-circle verified-badge" '
            'title="حساب موثق" aria-label="حساب موثق" role="img"></i>'
        )

    def linkify_hashtags(content):
        escaped_content = str(escape(unescape(content or '')))

        def replace_tag(match):
            tag = match.group(1)
            tag_url = url_for('explore.hashtag', tag=tag)
            return f'<a href="{escape(tag_url)}" class="hashtag-link">#{escape(tag)}</a>'

        return Markup(re.sub(r'(?<!&)#([\w\u0600-\u06FF]+)', replace_tag, escaped_content))

    from app.utils.helpers import parse_mentions, render_rich_text
    app.add_template_filter(linkify_hashtags, name='linkify_hashtags')
    app.add_template_filter(parse_mentions, name='parse_mentions')
    app.add_template_filter(render_rich_text, name='render_rich_text')

    # فلتر: يحوّل تاريخًا إلى تسمية عربية (اليوم، أمس، أو التاريخ الكامل)
    from datetime import date as _date, datetime as _dt

    def _anter_date_label(value):
        if value is None:
            return ''
        if isinstance(value, _dt):
            value = value.date()
        if not isinstance(value, _date):
            return str(value)
        today = _date.today()
        delta = (today - value).days
        if delta == 0:
            return 'اليوم'
        if delta == 1:
            return 'أمس'
        if delta == 2:
            return 'قبل يومين'
        if 3 <= delta <= 6:
            return f'قبل {delta} أيام'
        if 7 <= delta <= 13:
            return 'قبل أسبوع'
        if delta < 30:
            weeks = delta // 7
            return f'قبل {weeks} أسابيع'
        if delta < 365:
            months = delta // 30
            if months == 1:
                return 'قبل شهر'
            if months == 2:
                return 'قبل شهرين'
            return f'قبل {months} أشهر'
        years = delta // 365
        if years == 1:
            return 'قبل سنة'
        return f'قبل {years} سنوات'

    app.add_template_filter(_anter_date_label, name='date_label')
    app.add_template_global(verified_badge, name='verified_badge')

    # ============================================
    # تحديث آخر ظهور للمستخدم عند كل طلب
    # ============================================
    # ============================================
    # ANTER: تنظيف session في بداية كل طلب
    # يحمي من "connection مسمومة" في pool عند فشل أي commit سابق.
    # ============================================
    # ============================================================
    # Rate Limiting بسيط في الذاكرة (2026-09-27)
    # يعمل بكفاءة مع gunicorn --workers=1 --threads=1
    # ============================================================
    from collections import defaultdict
    from threading import Lock as _Lock

    _rate_lock = _Lock()
    _rate_buckets = defaultdict(list)

    _RATE_LIMITS = {
        # path_prefix: (max_requests, window_seconds)
        '/auth/login': (10, 60),           # 10 محاولات/دقيقة لكل IP
        '/auth/register': (5, 300),        # 5 تسجيلات/5 دقائق
        '/auth/reset_password': (10, 300), # 10 طلبات استعادة/5 دقائق
        '/auth/forgot': (10, 300),
        '/api/ai/assist': (20, 60),        # 20 طلب AI/دقيقة
        '/users/find-friends': (5, 60),    # 5 بحث جهات اتصال/دقيقة
        '/messages/send': (60, 60),        # 60 رسالة/دقيقة
    }

    def _client_ip():
        # Cloudflare / Render يضعون IP الحقيقي هنا
        xff = request.headers.get('X-Forwarded-For', '')
        if xff:
            return xff.split(',')[0].strip()
        return request.remote_addr or '0.0.0.0'

    def _check_rate_limit(path):
        for prefix, (limit, window) in _RATE_LIMITS.items():
            if not path.startswith(prefix):
                continue
            key = (_client_ip(), prefix)
            now = time.time()
            with _rate_lock:
                bucket = _rate_buckets[key]
                # نحذف الطلبات القديمة
                bucket[:] = [t for t in bucket if now - t < window]
                if len(bucket) >= limit:
                    return True, limit, window, len(bucket)
                bucket.append(now)
            return False, limit, window, len(bucket) + 1
        return False, 0, 0, 0

    @app.before_request
    def _anter_rate_limit():
        if request.path.startswith('/static/'):
            return
        limited, limit, window, count = _check_rate_limit(request.path)
        if limited:
            from flask import abort, make_response
            retry_after = window
            resp = make_response(
                f'<html><body style="font-family:sans-serif;text-align:center;'
                f'padding:60px 20px;direction:rtl"><h2>طلبات كثيرة جدًا</h2>'
                f'<p>حاول مجددًا بعد {retry_after} ثانية.</p></body></html>',
                429
            )
            resp.headers['Retry-After'] = str(retry_after)
            return resp

    @app.after_request
    def _anter_security_headers(response):
        """هيدرات أمان على كل الردود (2026-09-27)."""
        # منع تضمين الموقع في iframe خارجي
        response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
        # منع تخمين نوع المحتوى
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        # سياسة المُحيل
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        # عزل العملية (حماية ضد Spectre)
        response.headers.setdefault('Origin-Agent-Cluster', '?1')
        # منع المواقع الخارجية من تضمين مواردنا كصور/سكربتات
        response.headers.setdefault('Cross-Origin-Resource-Policy', 'same-origin')
        # عزل نافذة المتصفح (يمنع window.opener abuse)
        response.headers.setdefault('Cross-Origin-Opener-Policy', 'same-origin')
        # إلغاء ميزات المتصفح الحساسة
        response.headers.setdefault(
            'Permissions-Policy',
            'geolocation=(), microphone=(self), camera=(self), payment=()'
        )
        # إزالة هيدر Render الذي يكشف المنصة (2026-09-27)
        response.headers.pop('X-Render-Origin-Server', None)

        # HSTS: على HTTPS فقط (Render / Cloudflare)
        if request.is_secure:
            response.headers.setdefault(
                'Strict-Transport-Security',
                'max-age=31536000; includeSubDomains'
            )
        # CSP أساسية — لا تمنع أي شيء مستخدم حالياً
        # (نسمح بـ inline scripts لأن ANTER يستخدمها بكثافة)
        response.headers.setdefault(
            'Content-Security-Policy',
            "default-src 'self'; "
            "img-src 'self' data: https:; "
            "media-src 'self' https: blob:; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https:; "
            "style-src 'self' 'unsafe-inline'; "
            "font-src 'self' data:; "
            "connect-src 'self' https: wss:; "
            "frame-ancestors 'self'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "object-src 'none'; "
            "block-all-mixed-content; "
            "upgrade-insecure-requests"
        )
        return response

    @app.after_request
    def _anter_static_cache_and_compress(response):
        """Cache + gzip للملفات الثابتة النصية (CSS/JS/SVG)."""
        from flask import request as _req
        if not _req.path.startswith('/static/'):
            return response

        # ملفات مكتبات (Bootstrap, FontAwesome, Cairo) لا تتغير → cache طويل
        if _req.path.startswith('/static/vendor/'):
            response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
        else:
            response.headers['Cache-Control'] = 'public, max-age=3600'
        response.direct_passthrough = False

        if response.status_code != 200:
            return response
        if not _req.path.endswith(('.css', '.js', '.svg', '.json', '.txt', '.xml')):
            return response
        if 'Content-Encoding' in response.headers:
            return response

        accept = _req.headers.get('Accept-Encoding', '')

        try:
            data = response.get_data()
        except Exception:
            return response

        if not data or len(data) < 500:
            return response

        # نُفضّل Brotli (أصغر بـ 15–20%) ثم نرجع إلى gzip.
        compressed = None
        encoding = None

        if 'br' in accept:
            try:
                import brotli as _br
                compressed = _br.compress(data, quality=5)
                encoding = 'br'
            except Exception:
                compressed = None

        if compressed is None and 'gzip' in accept:
            import gzip as _gz
            compressed = _gz.compress(data, compresslevel=6)
            encoding = 'gzip'

        if compressed is None:
            return response

        response.set_data(compressed)
        response.headers['Content-Encoding'] = encoding
        response.headers['Content-Length'] = str(len(compressed))
        response.headers['Vary'] = 'Accept-Encoding'
        return response

    @app.before_request
    def _anter_clean_session():
        # تخطّي الملفات الثابتة — لا حاجة لتنظيف الـ session لطلب CSS/JS/صورة
        from flask import request as _req
        if _req.path.startswith('/static/'):
            return
        try:
            db.session.rollback()
        except Exception:
            pass

    @app.before_request
    def update_last_seen():
        from flask import request as _req
        from flask_login import current_user
        # تخطّي الملفات الثابتة — يمنع Vary:Cookie + Cache-Control:no-cache
        if _req.path.startswith('/static/'):
            return
        if not current_user.is_authenticated:
            return

        # لا نكتب في قاعدة البيانات مع كل طلب (خصوصًا طلبات polling للمكالمة).
        now = datetime.utcnow()
        last_seen = current_user.last_seen
        if last_seen and now - last_seen < timedelta(minutes=2):
            return

        current_user.last_seen = now
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    # ANTER: نغمة ترحيب بعد تسجيل الدخول/التسجيل/التبديل — تُقرأ مرة واحدة فقط.
    @app.context_processor
    def _inject_welcome_chime():
        try:
            play = session.pop('play_welcome_chime', False)
        except Exception:
            play = False
        return {'play_welcome_chime': bool(play)}

    return app
