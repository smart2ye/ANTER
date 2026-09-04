from flask import Flask
from .auth import auth_bp
from .main import main_bp
from .users import users_bp
from .posts import posts_bp
from .admin import admin_bp
from .messages import messages_bp
from .mobile_api import mobile_api_bp
from .notifications import notifications_bp
from .videos import videos_bp
from .explore import explore_bp
from .trends import trends_bp
from .media import media_bp
from .ai import ai_bp
from .sse import sse_bp
from .reactions import reactions_bp
from .stories import stories_bp

def register_blueprints(app: Flask):
    app.register_blueprint(stories_bp, url_prefix="/api")
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(main_bp)
    app.register_blueprint(users_bp, url_prefix='/users')
    app.register_blueprint(posts_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(messages_bp, url_prefix='/messages')
    app.register_blueprint(mobile_api_bp, url_prefix='/api/mobile')
    app.register_blueprint(notifications_bp, url_prefix='/notifications')
    app.register_blueprint(videos_bp, url_prefix='/videos')
    app.register_blueprint(explore_bp, url_prefix='/explore')
    app.register_blueprint(trends_bp, url_prefix='/trends')
    app.register_blueprint(media_bp, url_prefix='/media')
    app.register_blueprint(ai_bp, url_prefix='/api')
    app.register_blueprint(sse_bp, url_prefix='/sse')
    app.register_blueprint(reactions_bp)
