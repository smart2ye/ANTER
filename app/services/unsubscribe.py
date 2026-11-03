"""ANTER: إدارة إلغاء الاشتراك في رسائل البريد."""
import secrets

from app.extensions import db
from app.models import User


def get_or_create_token(user: User) -> str:
    """يعيد رمز إلغاء الاشتراك (وإن لم يوجد، ينشئه)."""
    if user.unsubscribe_token:
        return user.unsubscribe_token
    # توليد رمز عشوائي فريد
    for _ in range(10):
        token = secrets.token_urlsafe(32)[:64]
        if not User.query.filter_by(unsubscribe_token=token).first():
            user.unsubscribe_token = token
            db.session.commit()
            return token
    raise RuntimeError('unsubscribe: could not generate unique token')


def find_by_token(token: str):
    if not token or not isinstance(token, str):
        return None
    return User.query.filter_by(unsubscribe_token=token.strip()).first()


def unsubscribe(user: User) -> bool:
    """يضع علامة إلغاء الاشتراك. يعيد True إن نُفّذ."""
    if user.email_opted_out:
        return False
    user.email_opted_out = True
    db.session.commit()
    return True


def opt_in(user: User) -> bool:
    """يعيد الاشتراك."""
    if not user.email_opted_out:
        return False
    user.email_opted_out = False
    db.session.commit()
    return True
