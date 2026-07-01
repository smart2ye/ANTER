from flask import Flask, session
from app.config import Config
from app.extensions import db, login_manager, csrf
from app.models import User
from app.routes import register_blueprints
import os
import secrets

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    register_blueprints(app)

    # توليد مسار إداري سري
    admin_path = os.environ.get("ADMIN_PATH")
    if not admin_path:
        admin_path = "admin-" + secrets.token_urlsafe(10)
        os.environ["ADMIN_PATH"] = admin_path
    app.config["ADMIN_PATH"] = admin_path

    print(f"\n{'='*60}")
    print(f"🔐 مسار لوحة التحكم السري: /{admin_path}")
    print(f"📌 احفظ هذا المسار في مكان آمن!")
    print(f"{'='*60}\n")

    with app.app_context():
        db.create_all()

    # ============================================
    # دالة عامة لحساب التفاعلات (متاحة في كل القوالب)
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
    # معالج السياق (سياق التطبيق)
    # ============================================
    @app.before_request
    def update_last_seen():
        from flask_login import current_user
        from datetime import datetime
        if current_user.is_authenticated:
            current_user.last_seen = datetime.utcnow()
            db.session.commit()

    # ============================================
    # جعل get_status_icon متاحة في كل القوالب
    # ============================================
    @app.context_processor
    def inject_status_icon():
        from app.utils.helpers import get_status_icon
        return dict(get_status_icon=get_status_icon)

    return app
