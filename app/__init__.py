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


def _get_admin_path(config):
    """Return an explicit route or a fresh random route for this app startup."""
    configured_path = os.environ.get("ADMIN_PATH", "").strip().strip("/")
    if configured_path:
        return configured_path
    return f"admin-{secrets.token_urlsafe(24)}"


def create_app(test_config=None):
    app = Flask(__name__)
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
        escaped_content = str(escape(content or ''))

        def replace_tag(match):
            tag = match.group(1)
            tag_url = url_for('explore.hashtag', tag=tag)
            return f'<a href="{escape(tag_url)}" class="hashtag-link">#{escape(tag)}</a>'

        return Markup(re.sub(r'#([\w\u0600-\u06FF]+)', replace_tag, escaped_content))

    from app.utils.helpers import parse_mentions
    app.add_template_filter(linkify_hashtags, name='linkify_hashtags')
    app.add_template_filter(parse_mentions, name='parse_mentions')
    app.add_template_global(verified_badge, name='verified_badge')

    # ============================================
    # تحديث آخر ظهور للمستخدم عند كل طلب
    # ============================================
    @app.before_request
    def update_last_seen():
        from flask_login import current_user
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

    return app
