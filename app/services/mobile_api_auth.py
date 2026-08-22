import hashlib
import secrets
from datetime import datetime, timedelta
from functools import wraps

from flask import current_app, g, jsonify, request

from app.extensions import db
from app.models import MobileAccessToken, MobileBrowserAuthorization


def _token_hash(raw_token):
    return hashlib.sha256(raw_token.encode('utf-8')).hexdigest()


def issue_mobile_token(user, device_name='ANTER Messenger'):
    raw_token = secrets.token_urlsafe(48)
    lifetime = int(current_app.config['MOBILE_API_TOKEN_TTL_SECONDS'])
    token = MobileAccessToken(
        token_hash=_token_hash(raw_token),
        user_id=user.id,
        device_name=(device_name or 'ANTER Messenger').strip()[:120] or 'ANTER Messenger',
        expires_at=datetime.utcnow() + timedelta(seconds=lifetime),
    )
    db.session.add(token)
    db.session.commit()
    return raw_token, token


def issue_mobile_browser_authorization(user, state, redirect_uri, device_name='ANTER Messenger'):
    """يصدر رمز تفويض قصير العمر، ولا يحفظ قيمته الخام في قاعدة البيانات."""
    raw_code = secrets.token_urlsafe(32)
    lifetime = int(current_app.config['MOBILE_BROWSER_AUTH_CODE_TTL_SECONDS'])
    authorization = MobileBrowserAuthorization(
        code_hash=_token_hash(raw_code),
        state=(state or '').strip()[:120],
        redirect_uri=(redirect_uri or '').strip()[:255],
        user_id=user.id,
        device_name=(device_name or 'ANTER Messenger').strip()[:120] or 'ANTER Messenger',
        expires_at=datetime.utcnow() + timedelta(seconds=lifetime),
    )
    db.session.add(authorization)
    db.session.commit()
    return raw_code


def exchange_mobile_browser_authorization(code, state, redirect_uri):
    """يحوّل رمز المتصفح إلى رمز جهاز واحد فقط عند تطابق state ومسار العودة."""
    raw_code = (code or '').strip()
    if not raw_code or len(raw_code) > 512:
        return None
    authorization = MobileBrowserAuthorization.query.filter_by(code_hash=_token_hash(raw_code)).first()
    if (
        authorization is None
        or not authorization.is_valid
        or authorization.state != (state or '').strip()
        or authorization.redirect_uri != (redirect_uri or '').strip()
        or not authorization.user
        or not authorization.user.is_active
    ):
        return None

    raw_token = secrets.token_urlsafe(48)
    token_lifetime = int(current_app.config['MOBILE_API_TOKEN_TTL_SECONDS'])
    token = MobileAccessToken(
        token_hash=_token_hash(raw_token),
        user_id=authorization.user.id,
        device_name=authorization.device_name,
        expires_at=datetime.utcnow() + timedelta(seconds=token_lifetime),
    )
    authorization.consumed_at = datetime.utcnow()
    db.session.add(token)
    db.session.commit()
    return raw_token, token, authorization.user


def revoke_mobile_token(token):
    if token and token.revoked_at is None:
        token.revoked_at = datetime.utcnow()
        db.session.commit()


def current_mobile_token():
    header = request.headers.get('Authorization', '')
    if not header.startswith('Bearer '):
        return None
    raw_token = header[7:].strip()
    if not raw_token or len(raw_token) > 512:
        return None
    token = MobileAccessToken.query.filter_by(token_hash=_token_hash(raw_token)).first()
    if token is None or not token.is_valid or not token.user or not token.user.is_active:
        return None
    token.last_used_at = datetime.utcnow()
    db.session.commit()
    return token


def mobile_api_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        token = current_mobile_token()
        if token is None:
            return jsonify({'error': 'رمز الوصول غير صالح أو انتهت صلاحيته.'}), 401
        g.mobile_access_token = token
        g.mobile_user = token.user
        return view(*args, **kwargs)
    return wrapped
