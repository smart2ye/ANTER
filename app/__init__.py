from flask import Flask, flash, redirect, request, session, url_for
from werkzeug.exceptions import RequestEntityTooLarge
from app.config import Config
from app.extensions import db, login_manager, csrf
from app.models import User, CallSignal, CallLog, MobileAccessToken
from app.routes import register_blueprints
import hashlib
import hmac
import os
from datetime import datetime, timedelta


_ADMIN_PATH_SALT = b"anter-admin-path-v1"


def _get_admin_path(config):
    """Return an explicit route or a stable, non-logged fallback route."""
    configured_path = os.environ.get("ADMIN_PATH", "").strip().strip("/")
    if configured_path:
        return configured_path

    secret_key = str(config.get("SECRET_KEY", "")).encode("utf-8")
    if not secret_key:
        raise RuntimeError("SECRET_KEY must be configured before creating the application.")

    digest = hmac.new(secret_key, _ADMIN_PATH_SALT, hashlib.sha256).hexdigest()[:24]
    return f"admin-{digest}"


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # يبقى المسار ثابتاً عبر إعادة التشغيل ولا يُطبع في السجلات.
    # يمكن تدويره صراحةً عبر متغير البيئة ADMIN_PATH.
    app.config["ADMIN_PATH"] = _get_admin_path(app.config)

    register_blueprints(app)
    
    from app.routes.stories import stories_bp
    app.register_blueprint(stories_bp)

    @app.errorhandler(RequestEntityTooLarge)
    def handle_request_too_large(error):
        if request.path.startswith('/videos/upload'):
            max_video_mb = app.config['MAX_VIDEO_UPLOAD_BYTES'] // (1024 * 1024)
            flash(f'تعذر رفع الفيديو لأن حجمه أكبر من الحد المسموح ({max_video_mb} MB).', 'danger')
            return redirect(url_for('videos.upload'))
        return 'حجم الطلب أكبر من الحد المسموح.', 413

    with app.app_context():
        db.create_all()
        # إنشاء حساب مساعد أنتر الخدمي مرة واحدة وإعادة استخدامه في كل تشغيل.
        from app.services.anter_assistant import (
            ensure_anter_assistant_followed_by_all_users,
            ensure_anter_assistant_user,
        )
        ensure_anter_assistant_user()
        ensure_anter_assistant_followed_by_all_users()
        # إنشاء جداول القصص وإشارات وسجل المكالمات صراحةً على قواعد الإنتاج القائمة.
        CallSignal.__table__.create(bind=db.engine, checkfirst=True)
        CallLog.__table__.create(bind=db.engine, checkfirst=True)
        MobileAccessToken.__table__.create(bind=db.engine, checkfirst=True)
        from app.models.story import Story, StoryView
        Story.__table__.create(bind=db.engine, checkfirst=True)
        StoryView.__table__.create(bind=db.engine, checkfirst=True)
        # ترحيل خفيف للتوافق مع قواعد البيانات القائمة قبل دعم الرسائل الصوتية.
        from sqlalchemy import inspect, text
        inspector = inspect(db.engine)
        binary_type = 'BYTEA' if db.engine.dialect.name == 'postgresql' else 'BLOB'
        required_columns_by_table = {
            'messages': {
                'audio_path': 'VARCHAR(255)',
                'audio_data': binary_type,
                'audio_mime': 'VARCHAR(100)',
                'attachment_data': binary_type,
                'attachment_mime': 'VARCHAR(150)',
                'attachment_name': 'VARCHAR(255)',
                'attachment_kind': 'VARCHAR(20)',
            },
            'users': {
                'avatar_data': binary_type,
                'avatar_mime': 'VARCHAR(100)',
            },
            'posts': {
                'image_data': binary_type,
                'image_mime': 'VARCHAR(100)',
                'public_id': 'VARCHAR(40)',
                'link_url': 'VARCHAR(500)',
                'link_title': 'VARCHAR(255)',
                'link_description': 'TEXT',
                'link_image': 'VARCHAR(500)',
            },
            'videos': {
                'public_id': 'VARCHAR(40)',
            },
            'comments': {
                'audio_url': 'VARCHAR(255)',
            },
            'messages': {
                'parent_id': 'INTEGER',
                'is_deleted_everyone': 'BOOLEAN DEFAULT FALSE',
                'deleted_by_sender': 'BOOLEAN DEFAULT FALSE',
                'deleted_by_receiver': 'BOOLEAN DEFAULT FALSE',
            },
        }
        with db.engine.begin() as connection:
            for table_name, required_columns in required_columns_by_table.items():
                if table_name not in inspector.get_table_names():
                    continue
                columns = {column['name'] for column in inspector.get_columns(table_name)}
                for name, sql_type in required_columns.items():
                    if name not in columns:
                        connection.execute(text(
                            f'ALTER TABLE {table_name} ADD COLUMN {name} {sql_type}'
                        ))

            # إضافة فهارس فريدة للروابط العامة في قواعد البيانات القائمة.
        with db.engine.begin() as connection:
            for table_name in ('posts', 'videos'):
                if table_name in inspector.get_table_names():
                    connection.execute(text(
                        f'CREATE UNIQUE INDEX IF NOT EXISTS ix_{table_name}_public_id ON {table_name} (public_id)'
                    ))

        # ترحيل البيانات القائمة إلى معرّفات عامة لا تكشف الرقم التسلسلي.
        from app.models import Post, Video
        from app.utils.public_ids import generate_public_id
        for model, prefix in ((Post, 'p'), (Video, 'r')):
            for entity in model.query.filter(model.public_id.is_(None)).all():
                public_id = generate_public_id(prefix)
                while model.query.filter_by(public_id=public_id).first() is not None:
                    public_id = generate_public_id(prefix)
                entity.public_id = public_id
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
