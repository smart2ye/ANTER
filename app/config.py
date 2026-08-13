import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DEFAULT_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, '../instance/anter.db')
DATABASE_URI = os.environ.get('DATABASE_URL') or os.environ.get('SQLALCHEMY_DATABASE_URI') or DEFAULT_DATABASE_URI
if DATABASE_URI.startswith('postgres://'):
    DATABASE_URI = DATABASE_URI.replace('postgres://', 'postgresql://', 1)

DEFAULT_UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static/uploads')
UPLOAD_FOLDER = os.path.abspath(os.environ.get('UPLOAD_FOLDER', DEFAULT_UPLOAD_FOLDER))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = DATABASE_URI
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 280,
    }
    UPLOAD_FOLDER = UPLOAD_FOLDER
    MAX_CONTENT_LENGTH = 200 * 1024 * 1024
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'webm', 'avi', 'mov', 'mkv'}
    ALLOWED_AUDIO_EXTENSIONS = {'webm', 'ogg', 'mp3', 'wav', 'm4a', 'aac'}
    WEBRTC_STUN_URL = os.environ.get('WEBRTC_STUN_URL', 'stun:stun.l.google.com:19302')
    WEBRTC_TURN_URL = os.environ.get('WEBRTC_TURN_URL', '')
    WEBRTC_TURN_USERNAME = os.environ.get('WEBRTC_TURN_USERNAME', '')
    WEBRTC_TURN_CREDENTIAL = os.environ.get('WEBRTC_TURN_CREDENTIAL', '')
    PERMANENT_SESSION_LIFETIME = 86400


for subfolder in ('avatars', 'posts', 'reels', 'videos', 'thumbnails', 'audio'):
    os.makedirs(os.path.join(UPLOAD_FOLDER, subfolder), exist_ok=True)
