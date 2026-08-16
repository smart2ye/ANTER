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


def env_int(name, default, minimum=1):
    """Read a positive integer from the environment without risking startup failure."""
    try:
        return max(minimum, int(os.environ.get(name, default)))
    except (TypeError, ValueError):
        return default


if DATABASE_URI.startswith('sqlite'):
    DATABASE_ENGINE_OPTIONS = {
        'connect_args': {'check_same_thread': False, 'timeout': 30},
    }
else:
    DATABASE_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 280,
    }


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = DATABASE_URI
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = DATABASE_ENGINE_OPTIONS
    UPLOAD_FOLDER = UPLOAD_FOLDER
    # Video files are streamed to a temporary file by Werkzeug, then saved directly to disk.
    # Keep a small overhead above the video cap for multipart form data and a thumbnail.
    MAX_CONTENT_LENGTH = env_int('MAX_REQUEST_BYTES', 55 * 1024 * 1024, 10 * 1024 * 1024)
    MAX_VIDEO_UPLOAD_BYTES = env_int('MAX_VIDEO_UPLOAD_BYTES', 50 * 1024 * 1024, 5 * 1024 * 1024)
    MAX_AUDIO_MESSAGE_BYTES = 10 * 1024 * 1024
    # Admission limits protect a small worker from oversized or highly compressed uploads.
    MAX_IMAGE_BYTES = env_int('MAX_IMAGE_BYTES', 5 * 1024 * 1024, 1 * 1024 * 1024)
    MAX_IMAGE_PIXELS = env_int('MAX_IMAGE_PIXELS', 10 * 1024 * 1024, 1 * 1024 * 1024)
    MAX_CHAT_ATTACHMENT_BYTES = 8 * 1024 * 1024
    # Keep the initial HTML response small; additional posts load on scroll.
    FEED_PAGE_SIZE = env_int('FEED_PAGE_SIZE', 5, 2)
    FEED_CANDIDATE_LIMIT = env_int('FEED_CANDIDATE_LIMIT', 30, FEED_PAGE_SIZE)
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'webm', 'avi', 'mov', 'mkv'}
    ALLOWED_AUDIO_EXTENSIONS = {'webm', 'ogg', 'mp3', 'wav', 'm4a', 'aac'}
    ALLOWED_CHAT_FILE_EXTENSIONS = {'pdf', 'txt', 'doc', 'docx', 'xls', 'xlsx', 'zip'}
    WEBRTC_STUN_URL = os.environ.get('WEBRTC_STUN_URL', 'stun:stun.l.google.com:19302')
    WEBRTC_TURN_URL = os.environ.get('WEBRTC_TURN_URL', '')
    WEBRTC_TURN_USERNAME = os.environ.get('WEBRTC_TURN_USERNAME', '')
    WEBRTC_TURN_CREDENTIAL = os.environ.get('WEBRTC_TURN_CREDENTIAL', '')
    PERMANENT_SESSION_LIFETIME = 86400
    
    # مفاتيح الذكاء الاصطناعي (Hybrid AI)
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')


for subfolder in ('avatars', 'posts', 'reels', 'videos', 'thumbnails', 'audio'):
    os.makedirs(os.path.join(UPLOAD_FOLDER, subfolder), exist_ok=True)
