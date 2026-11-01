"""ANTER: خدمة إعدادات الموقع — قراءة/كتابة key/value + كاش بسيط في الذاكرة."""

import re

import bleach

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


# ANTER: قائمة بيضاء صارمة لـHTML في الإعلان (بلا style مباشر — أصناف محددة)
_ALLOWED_TAGS = ['b', 'strong', 'i', 'em', 'u', 'br', 'span']
_ALLOWED_ATTRS = {
    'span': ['class'],
}
_ALLOWED_CLASSES = {'c-cyan', 'c-gold', 'c-white', 'c-red', 'c-green', 'c-purple'}


def _sanitize_html(raw: str) -> str:
    """يُنظّف HTML الإعلان ويُبقي التنسيق فقط (بلا XSS، بلا style مباشر)."""
    if not raw:
        return ''
    try:
        cleaned = bleach.clean(
            raw,
            tags=_ALLOWED_TAGS,
            attributes=_ALLOWED_ATTRS,
            strip=True,
        )
        # نُبقي فقط أصناف الألوان المسموحة (حماية مزدوجة)
        def _filter_class(match):
            classes = match.group(1).split()
            allowed = [c for c in classes if c in _ALLOWED_CLASSES]
            if not allowed:
                return ''
            return ' class="' + ' '.join(allowed) + '"'
        cleaned = re.sub(r'\s+class="([^"]*)"', _filter_class, cleaned)
        return cleaned
    except Exception:
        return ''


def _format_text(raw: str) -> str:
    """يستبدل {name} / {first_name} / {username} بقيم المستخدم الحالي.

    - للمسجلين: القيم الفعلية.
    - للزوار: حذف المتغيرات مع تنظيف الفراغات والشرطات المعلقة.
    - لا يستخدم Jinja — استبدال نصي آمن ضد الحقن.
    """
    if not raw:
        return ''
    # 1. تنظيف HTML أولًا (قبل استبدال المتغيرات — يمنع حقن عبر اسم المستخدم)
    raw = _sanitize_html(raw)
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
        # للزوار: حذف المتغيرات، ثم حذف الوسوم التي أصبحت فارغة
        text = raw
        text = re.sub(r'\s*[—\\-|/]\s*\{username\}\s*[—\\-|/]\s*', ' ', text)
        text = text.replace('{username}', '')
        text = text.replace('{name}', '')
        text = text.replace('{first_name}', '')
        # حذف الوسوم الفارغة (مثل <strong></strong>)
        for _ in range(3):
            text = re.sub(r'<(strong|b|em|i|u|span)(\s[^>]*)?>\s*</\1>', '', text)
        # حذف الشرطات المزدوجة والمعلقة
        text = re.sub(r'\s*—\s*—\s*', ' — ', text)
        text = re.sub(r'\s+', ' ', text)
        text = text.strip(' —')
    # تنظيف خفيف: مسافات متعددة فقط (داخل النص، لا بين الوسوم)
    text = re.sub(r'[ \t]+', ' ', text)
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


# ============================================================
# ANTER: إعلانات الشريط المتحرك (متعددة)
# ============================================================
def get_active_announcements():
    """يعيد قائمة الإعلانات النشطة (مرتبة) كـstrings بعد التنسيق."""
    try:
        from app.models import Announcement
        rows = (
            Announcement.query
            .filter(Announcement.is_active.is_(True))
            .order_by(Announcement.sort_order.asc(), Announcement.id.asc())
            .all()
        )
    except Exception:
        rows = []

    out = []
    for row in rows:
        formatted = _format_text(row.text or '')
        if formatted:
            out.append(formatted)
    return out


def save_announcement_item(item_id, text, sort_order, is_active):
    """يحفظ إعلاناً (جديد أو تعديل). يعيد id."""
    from app.models import Announcement
    if item_id:
        item = Announcement.query.get(int(item_id))
        if not item:
            raise ValueError('not found')
    else:
        item = Announcement()
        db.session.add(item)
    item.text = (text or '').strip()[:500]
    item.sort_order = int(sort_order or 0)
    item.is_active = bool(is_active)
    db.session.commit()
    return item.id


def delete_announcement_item(item_id):
    from app.models import Announcement
    item = Announcement.query.get(int(item_id))
    if not item:
        return False
    db.session.delete(item)
    db.session.commit()
    return True
