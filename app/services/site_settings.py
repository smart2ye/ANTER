"""ANTER: خدمة إعدادات الموقع — قراءة/كتابة key/value + كاش بسيط في الذاكرة."""

import re

from app.extensions import db
from app.models import SiteSetting


# مفاتيح معروفة (لتجنّب الأخطاء المطبعية)
KEY_ANNOUNCEMENT_TEXT = 'announcement_text'
KEY_ANNOUNCEMENT_ENABLED = 'announcement_enabled'

DEFAULTS = {
    KEY_ANNOUNCEMENT_TEXT: '',
    KEY_ANNOUNCEMENT_ENABLED: '1',
}

# كاش بسيط في العملية — يُبطَّل عند الحفظ
_cache = {}


def _get(key: str) -> str:
    if key in _cache:
        return _cache[key]
    try:
        row = SiteSetting.query.filter_by(key=key).first()
        if row is None:
            return DEFAULTS.get(key, '')
        _cache[key] = row.value or ''
        return _cache[key]
    except Exception:
        return DEFAULTS.get(key, '')


def _set(key: str, value: str) -> None:
    try:
        row = SiteSetting.query.filter_by(key=key).first()
        if row is None:
            row = SiteSetting(key=key, value=value or '')
            db.session.add(row)
        else:
            row.value = value or ''
        db.session.commit()
        _cache[key] = value or ''
    except Exception:
        db.session.rollback()
        raise


def _format_text(raw: str) -> str:
    """يستبدل {name} / {first_name} / {username} بقيم المستخدم الحالي.

    - للمسجلين: القيم الفعلية.
    - للزوار: حذف المتغيرات مع تنظيف الفراغات والشرطات المعلقة.
    - لا يستخدم Jinja — استبدال نصي آمن ضد الحقن.
    """
    if not raw:
        return ''
    try:
        from flask_login import current_user
        is_authed = getattr(current_user, 'is_authenticated', False)
    except Exception:
        is_authed = False

    if is_authed:
        full_name = (getattr(current_user, 'name', '') or '').strip() or (getattr(current_user, 'username', '') or '')
        first = full_name.split()[0] if full_name else ''
        uname = (getattr(current_user, 'username', '') or '').strip()
        text = raw
        text = text.replace('{name}', full_name)
        text = text.replace('{first_name}', first)
        text = text.replace('{username}', ('@' + uname) if uname else '')
    else:
        # للزوار: حذف متغير {username} مع الشرطات المحيطة، ثم بقية المتغيرات
        text = raw
        text = re.sub(r'\s*[—\-|/]\s*\{username\}\s*[—\-|/]\s*', ' ', text)
        text = text.replace('{username}', '')
        text = text.replace('{name}', '')
        text = text.replace('{first_name}', '')

    # تنظيف عام (المسافات + الشرطات المعلقة + المسافة قبل الترقيم)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\s*—\s*—', ' —', text)
    text = text.strip(' —')
    text = re.sub(r'\s+([.,!؟…])', r'\1', text)
    text = text.strip()
    return text


def get_announcement() -> dict:
    """يعيد dict: {text, enabled}. يستبدل المتغيرات بقيم المستخدم الحالي."""
    raw = _get(KEY_ANNOUNCEMENT_TEXT).strip()
    enabled_raw = _get(KEY_ANNOUNCEMENT_ENABLED)
    enabled = enabled_raw not in ('0', 'false', 'False', 'no', '')
    if not raw:
        enabled = False
    return {'text': _format_text(raw), 'enabled': enabled}


def save_announcement(text: str, enabled: bool) -> None:
    _set(KEY_ANNOUNCEMENT_TEXT, (text or '').strip()[:500])
    _set(KEY_ANNOUNCEMENT_ENABLED, '1' if enabled else '0')


def invalidate_cache() -> None:
    _cache.clear()
