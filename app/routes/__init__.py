from .auth import auth_bp
from .main import main_bp
from .posts import posts_bp
from .users import users_bp
from .explore import explore_bp
from .messages import messages_bp
from .notifications import notifications_bp
from .sse import sse_bp
from .admin import admin_bp
from .videos import videos_bp
from .trends import trends_bp
from .api import api_bp
from .media import media_bp
from .ai import ai_bp
from .mobile_api import mobile_api_bp

def register_blueprints(app):
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(posts_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(explore_bp)
    app.register_blueprint(messages_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(sse_bp)
    app.register_blueprint(admin_bp, url_prefix='/' + app.config.get('ADMIN_PATH', 'admin'))
    app.register_blueprint(videos_bp)
    app.register_blueprint(trends_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(media_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(mobile_api_bp)
