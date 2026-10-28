"""ANTER: نظام الإحالة.

- يمنح كل مستخدم كودًا فريدًا (lazy) لاستخدامه في رابط الدعوة.
- عند تأكيد بريد أو جوال المُحال، يُحتسب للمُحيل مرة واحدة فقط.
- عند وصول المُحيل إلى 5 إحالات مكتملة → يُوثَّق تلقائيًا.
"""
import secrets
import string

from flask import current_app

from app.extensions import db
from app.models import User, Notification


_CODE_ALPHABET = string.ascii_uppercase + string.digits
_CODE_LENGTH = 8
_VERIFY_THRESHOLD = 5


def _generate_code() -> str:
    """كود عشوائي 8 أحرف (A-Z0-9) — محاولات محدودة لتجنّب التصادم."""
    for _ in range(20):
        code = ''.join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))
        exists = User.query.filter_by(referral_code=code).first()
        if not exists:
            return code
    raise RuntimeError('referral: could not generate unique code after 20 attempts')


def get_or_create_referral_code(user: User) -> str:
    """يُرجع كود المستخدم، وينشئه عند أول طلب. لا يحفظ إن كان موجودًا."""
    if user.referral_code:
        return user.referral_code
    user.referral_code = _generate_code()
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        # محاولة أخرى — قد يكون سباقًا نادرًا
        user.referral_code = _generate_code()
        db.session.commit()
    return user.referral_code


def find_by_code(code: str):
    """يبحث عن مستخدم بكود الإحالة (بلا حساسية لحالة الأحرف)."""
    if not code or not isinstance(code, str):
        return None
    normalized = code.strip().upper()
    if not normalized or len(normalized) > 12:
        return None
    return User.query.filter_by(referral_code=normalized).first()


def credit_referral_if_verified(user: User) -> None:
    """يُستدعى بعد تأكيد بريد أو جوال. يحتسب الإحالة مرة واحدة فقط.

    الشروط:
    - referred_by_id موجود.
    - المُحال لم يُحتسب له سابقًا (referral_credited == False).
    - المُحال مؤكد البريد أو الجوال.
    """
    if not user.referred_by_id:
        return
    if user.referral_credited:
        return
    if not (user.email_verified or user.phone_verified):
        return

    referrer = User.query.get(user.referred_by_id)
    if not referrer or referrer.id == user.id:
        return

    referrer.referral_count = (referrer.referral_count or 0) + 1
    user.referral_credited = True

    try:
        db.session.add(Notification(
            user_id=referrer.id,
            actor_id=user.id,
            action='referral_credited',
            extra_text=f'انضم {user.name or user.username} عبر دعوتك. لديك الآن {referrer.referral_count}/5.',
        ))

        # التوثيق التلقائي عند بلوغ 5 إحالات — يحترم verification_locked
        if (referrer.referral_count >= _VERIFY_THRESHOLD
                and not referrer.is_verified
                and not referrer.verification_locked):
            referrer.is_verified = True
            referrer.verification_source = 'referral'
            db.session.add(Notification(
                user_id=referrer.id,
                actor_id=referrer.id,
                action='verification_approved',
                extra_text='🎉 تهانينا! حصلت على التوثيق تلقائيًا بعد إتمام 5 إحالات ناجحة.',
            ))
            try:
                current_app.logger.info(
                    'referral: auto-verified user id=%s after %s referrals',
                    referrer.id, referrer.referral_count,
                )
            except Exception:
                pass

        db.session.commit()
    except Exception:
        db.session.rollback()
        try:
            current_app.logger.exception('referral: credit failed for user id=%s', user.id)
        except Exception:
            pass
