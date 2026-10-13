"""رموز إعادة تعيين كلمة السر — تمنع إعادة الاستخدام.

الحل: نُدرج جزءًا من password_hash في الرمز.
- عند توليد الرمز: نُوقّع user_id + آخر 20 حرفًا من password_hash.
- عند التحقق: نقارن ما في الرمز بالـ password_hash الحالي.
- بعد تغيير كلمة السر: يتغير password_hash → الرمز القديم يفشل.
"""
from __future__ import annotations

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.extensions import db
from app.models import User


SALT = 'password-reset'
MAX_AGE = 48 * 60 * 60  # 48 ساعة


def _serializer():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'])


def _payload_for(user: User) -> str:
    """user_id + آخر 20 حرفًا من password_hash (أو 'none' لو فارغ)."""
    suffix = (user.password_hash or '')[-20:] or 'none'
    return f'{user.id}:{suffix}'


def generate_token(user: User) -> str:
    """يولّد رمزًا مرتبطًا بكلمة السر الحالية."""
    return _serializer().dumps(_payload_for(user), salt=SALT)


def verify_token(token: str) -> User | None:
    """يتحقق من الرمز ويُعيد المستخدم — أو None لو فشل."""
    try:
        payload = _serializer().loads(token, salt=SALT, max_age=MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None

    try:
        user_id_str, suffix = payload.split(':', 1)
        user_id = int(user_id_str)
    except (ValueError, AttributeError):
        return None

    user = db.session.get(User, user_id)
    if not user:
        return None

    current_suffix = (user.password_hash or '')[-20:] or 'none'
    if current_suffix != suffix:
        # كلمة السر تغيّرت بعد إصدار الرمز → الرمز لاغٍ.
        return None

    return user
