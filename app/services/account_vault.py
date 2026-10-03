"""إدارة الحسابات المحفوظة — للتبديل السريع بين الحسابات.

تخزين: كوكي واحد 'anter_accounts' يحوي قائمة [{user_id, token, name, username, avatar_id}].
الأمان: كل token موقّع بـ SECRET_KEY + password_hash للمستخدم.
صلاحية: 30 يومًا.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from flask import current_app, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.extensions import db
from app.models import User


COOKIE_NAME = 'anter_accounts'
MAX_ACCOUNTS = 5
TOKEN_MAX_AGE = 60 * 60 * 24 * 30  # 30 يومًا


def _serializer():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'])


def _sign_for_user(user):
    """يُنشئ token موقّعًا لاستخدامه لاحقًا في التبديل."""
    # نُدمج hash كلمة السر — إن تغيّرت، يصبح الـ token غير صالح.
    payload = f'{user.id}:{(user.password_hash or "")[-20:]}'
    return _serializer().dumps(payload, salt='account-vault')


def _user_from_token(token):
    """يتحقق من token ويُعيد المستخدم أو None."""
    try:
        payload = _serializer().loads(token, salt='account-vault', max_age=TOKEN_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    try:
        user_id_str, ph_suffix = payload.split(':', 1)
        user_id = int(user_id_str)
    except (ValueError, AttributeError):
        return None
    user = db.session.get(User, user_id)
    if not user:
        return None
    if (user.password_hash or '')[-20:] != ph_suffix:
        return None  # كلمة السر تغيّرت → الرمز لاغٍ
    return user


def get_saved_accounts():
    """يُعيد قائمة الحسابات المحفوظة (بلا فك تشفير)."""
    raw = request.cookies.get(COOKIE_NAME)
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    return data[:MAX_ACCOUNTS]


def _write_accounts(accounts, response):
    """يكتب القائمة في الكوكي."""
    payload = json.dumps(accounts[:MAX_ACCOUNTS], ensure_ascii=False, separators=(',', ':'))
    max_age = TOKEN_MAX_AGE
    response.set_cookie(
        COOKIE_NAME,
        payload,
        max_age=max_age,
        httponly=True,
        secure=current_app.config.get('SESSION_COOKIE_SECURE', False),
        samesite='Lax',
        path='/',
    )


def add_account(user, response):
    """يُضيف أو يُحدّث حسابًا في القائمة."""
    accounts = get_saved_accounts()
    # أزل الحساب إن كان موجودًا (نُحدّث موقعه)
    accounts = [a for a in accounts if a.get('user_id') != user.id]

    accounts.insert(0, {
        'user_id': user.id,
        'token': _sign_for_user(user),
        'username': user.username,
        'name': user.name or user.username,
        'avatar_id': user.id,
        'saved_at': datetime.utcnow().isoformat(timespec='seconds'),
    })
    _write_accounts(accounts, response)


def remove_account(user_id, response):
    """يُزيل حسابًا من القائمة."""
    accounts = [a for a in get_saved_accounts() if a.get('user_id') != user_id]
    _write_accounts(accounts, response)


def clear_accounts(response):
    """يمسح كل الحسابات."""
    response.delete_cookie(COOKIE_NAME, path='/')


def resolve_switch_token(token):
    """يتحقق من token ويُعيد المستخدم للتبديل."""
    return _user_from_token(token)


def enrich_accounts(accounts):
    """يُثري كل حساب ببيانات إضافية (avatar_url، is_current) من القاعدة."""
    from flask_login import current_user
    from app.utils.media_urls import avatar_url

    result = []
    current_id = current_user.id if current_user.is_authenticated else None
    for acc in accounts:
        user = db.session.get(User, acc.get('user_id'))
        if not user:
            continue
        result.append({
            'user_id': user.id,
            'username': user.username,
            'name': user.name or user.username,
            'avatar_url': avatar_url(user),
            'token': acc.get('token', ''),
            'is_current': user.id == current_id,
            'is_online': bool(
                user.last_seen and
                (datetime.utcnow() - user.last_seen).total_seconds() < 300
            ),
        })
    return result
