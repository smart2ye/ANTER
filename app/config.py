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


def env_float(name, default, minimum=1.0, maximum=60.0):
    """Read a bounded float from the environment without risking startup failure."""
    try:
        value = float(os.environ.get(name, default))
    except (TypeError, ValueError):
        value = default
    return min(max(value, minimum), maximum)


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
    # رموز تطبيق ANTER Messenger تخص جهازاً واحداً ولا تُحفظ قيمتها الخام في قاعدة البيانات.
    MOBILE_API_TOKEN_TTL_SECONDS = env_int('MOBILE_API_TOKEN_TTL_SECONDS', 43200, 900)
    MOBILE_API_MAX_MESSAGE_CHARS = env_int('MOBILE_API_MAX_MESSAGE_CHARS', 2000, 100)
    MOBILE_API_TYPING_TTL_SECONDS = env_int('MOBILE_API_TYPING_TTL_SECONDS', 8, 3)
    PERMANENT_SESSION_LIFETIME = 86400
    
    # مفاتيح الذكاء الاصطناعي (Hybrid AI)
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

    # mini-llm Arabic: مسار كتابة ANTER للمحتوى والتحسين. تبقى القيم الفعلية في بيئة الخادم فقط.
    MINI_LLM_ARABIC_ENABLED = os.environ.get('MINI_LLM_ARABIC_ENABLED', 'true').strip().lower() == 'true'
    MINI_LLM_ARABIC_API_URL = os.environ.get(
        'MINI_LLM_ARABIC_API_URL',
        'https://api.groq.com/openai/v1/chat/completions',
    ).strip()
    MINI_LLM_ARABIC_API_KEY = os.environ.get('MINI_LLM_ARABIC_API_KEY', os.environ.get('GROQ_API_KEY', '')).strip()
    MINI_LLM_ARABIC_MODEL = os.environ.get(
        'MINI_LLM_ARABIC_MODEL', os.environ.get('GROQ_MODEL', 'qwen/qwen3.6-27b')
    ).strip() or 'qwen/qwen3.6-27b'
    MINI_LLM_ARABIC_TIMEOUT_SECONDS = env_float('MINI_LLM_ARABIC_TIMEOUT_SECONDS', 30.0, 5.0, 60.0)

    # مساعد أنتر داخل الرسائل: الإعدادات سرّية وتأتي من .env أو بيئة Render.
    ANTER_ASSISTANT_ENABLED = os.environ.get('ANTER_ASSISTANT_ENABLED', 'true').strip().lower() == 'true'
    ANTER_ASSISTANT_DAILY_POSTS_ENABLED = os.environ.get('ANTER_ASSISTANT_DAILY_POSTS_ENABLED', 'true').strip().lower() == 'true'
    ANTER_ASSISTANT_USERNAME = os.environ.get('ANTER_ASSISTANT_USERNAME', 'anter_assistant').strip() or 'anter_assistant'
    ANTER_ASSISTANT_EMAIL = os.environ.get('ANTER_ASSISTANT_EMAIL', 'assistant@anter.local').strip() or 'assistant@anter.local'
    ANTER_ASSISTANT_NAME = os.environ.get('ANTER_ASSISTANT_NAME', 'مساعد أنتر').strip() or 'مساعد أنتر'
    # كلمة مرور مراجعة بشرية اختيارية؛ لا توضع في Git وتُضبط محلياً أو في بيئة Render فقط.
    ANTER_ASSISTANT_REVIEW_PASSWORD = os.environ.get('ANTER_ASSISTANT_REVIEW_PASSWORD', '')
    ANTER_FOUNDER_NAME = os.environ.get('ANTER_FOUNDER_NAME', 'عبدالقادر مهدلي').strip() or 'عبدالقادر مهدلي'
    # إصدار Android المنشور من ANTER Messenger؛ يمكن استبداله في بيئة الإنتاج عند إصدار نسخة أحدث.
    ANTER_MESSENGER_APK_URL = os.environ.get(
        'ANTER_MESSENGER_APK_URL',
        'https://files.manuscdn.com/user_upload_by_module/session_file/310519663194595954/tUwimvKdwnQPBUdy.apk',
    ).strip()
    ANTER_MESSENGER_APK_SHA256 = os.environ.get(
        'ANTER_MESSENGER_APK_SHA256',
        '67abc0d424e971f0429687e5f495411346ba950c6cf957f2ccafe6558614e071',
    ).strip().lower()
    ANTER_MESSENGER_VERSION = os.environ.get('ANTER_MESSENGER_VERSION', '1.1.0').strip() or '1.1.0'
    ANTER_MESSENGER_RELEASE_NOTES = os.environ.get(
        'ANTER_MESSENGER_RELEASE_NOTES', 'إصدار رسمي: دخول عبر موقع ANTER، واجهة مراسلة موحّدة، وتحسينات في التحديثات.'
    ).strip()
    # حساب المؤسس الوحيد المسموح له بتبديل الجلسة إلى حساب مساعد أنتر.
    ANTER_ASSISTANT_SWITCH_OWNER_USERNAME = os.environ.get(
        'ANTER_ASSISTANT_SWITCH_OWNER_USERNAME', 'abdulqader.mahdly'
    ).strip().lstrip('@') or 'abdulqader.mahdly'
    # حساب مالك ANTER المسموح بترقيته إلى مدير عند بدء التشغيل. لا ينشئ هذا
    # إعداداً مساراً عاماً ولا يتعامل مع كلمات المرور.
    ANTER_OWNER_ADMIN_USERNAME = os.environ.get(
        'ANTER_OWNER_ADMIN_USERNAME', 'abdulqader.mahdly'
    ).strip().lstrip('@')
    ANTER_ASSISTANT_MAX_QUESTION_CHARACTERS = env_int('ANTER_ASSISTANT_MAX_QUESTION_CHARACTERS', 1200, 100)
    ANTER_ASSISTANT_MAX_REPLY_CHARACTERS = env_int('ANTER_ASSISTANT_MAX_REPLY_CHARACTERS', 1200, 300)
    ANTER_ASSISTANT_MINI_LLM_ARABIC_API_KEY = os.environ.get(
        'ANTER_ASSISTANT_MINI_LLM_ARABIC_API_KEY', MINI_LLM_ARABIC_API_KEY
    ).strip()
    ANTER_ASSISTANT_MINI_LLM_ARABIC_MODEL = os.environ.get(
        'ANTER_ASSISTANT_MINI_LLM_ARABIC_MODEL', MINI_LLM_ARABIC_MODEL
    ).strip() or MINI_LLM_ARABIC_MODEL
    ANTER_ASSISTANT_MINI_LLM_ARABIC_TIMEOUT_SECONDS = env_float(
        'ANTER_ASSISTANT_MINI_LLM_ARABIC_TIMEOUT_SECONDS', 40.0, 5.0, 60.0
    )
    ANTER_ASSISTANT_MINI_LLM_ARABIC_MAX_TOKENS = env_int(
        'ANTER_ASSISTANT_MINI_LLM_ARABIC_MAX_TOKENS', 420, 120
    )

    # تفويض Messenger عبر متصفح ANTER: لا تصل كلمة المرور إلى التطبيق.
    MOBILE_BROWSER_AUTH_CODE_TTL_SECONDS = env_int('MOBILE_BROWSER_AUTH_CODE_TTL_SECONDS', 180, 60)
    MOBILE_BROWSER_AUTH_REDIRECT_URI = os.environ.get(
        'MOBILE_BROWSER_AUTH_REDIRECT_URI', 'anter-messenger://auth/callback'
    ).strip()


for subfolder in ('avatars', 'posts', 'reels', 'videos', 'thumbnails', 'audio'):
    os.makedirs(os.path.join(UPLOAD_FOLDER, subfolder), exist_ok=True)
