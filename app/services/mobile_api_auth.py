import hashlib
import secrets
from datetime import datetime, timedelta
from functools import wraps

from flask import current_app, g, jsonify, request

from app.extensions import db
from app.models import MobileAccessToken


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

