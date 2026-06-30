import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, '../instance/anter.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static/uploads')
    MAX_CONTENT_LENGTH = 200 * 1024 * 1024
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'webm', 'avi', 'mov', 'mkv'}
    PERMANENT_SESSION_LIFETIME = 86400

os.makedirs(os.path.join(BASE_DIR, 'static/uploads/avatars'), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, 'static/uploads/posts'), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, 'static/uploads/reels'), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, 'static/uploads/videos'), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, 'static/uploads/thumbnails'), exist_ok=True)
