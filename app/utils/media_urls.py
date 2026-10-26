import os

from flask import current_app, url_for


def _legacy_static_url(path, default='default.png'):
    if path and str(path).startswith('img/'):
        return url_for('static', filename=path)
    if path:
        full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], path)
        if os.path.isfile(full_path):
            return url_for('static', filename=f'uploads/{path}')
    return url_for('static', filename=f'uploads/{default}')


_DEFAULT_MALE = 'img/default_avatar_male.webp'
_DEFAULT_FEMALE = 'img/default_avatar_female.webp'
_LEGACY_DEFAULT = 'default.png'

# كل مسارات الصور الافتراضية (القديمة والجديدة) — نُجاهلها لاختيار الصورة حسب الجنس.
_DEFAULT_AVATAR_PATHS = {
    'default.png',
    'img/default_avatar_male.png',
    'img/default_avatar_female.png',
    'img/default_avatar_male.webp',
    'img/default_avatar_female.webp',
}


def avatar_url(user):
    # ANTER: نفحص avatar_mime بدل avatar_data — يعمل حتى لو لم يُحمَّل الـ BLOB.
    if getattr(user, 'avatar_mime', None):
        return url_for('media.avatar', user_id=user.id)

    avatar = getattr(user, 'avatar', None)
    # صورة مخصصة رفعها المستخدم (ليست أي صورة افتراضية)
    if avatar and avatar not in _DEFAULT_AVATAR_PATHS:
        return _legacy_static_url(avatar)

    # افتراضي حسب الجنس
    gender = (getattr(user, 'gender', '') or '').lower()
    if gender == 'female':
        return url_for('static', filename=_DEFAULT_FEMALE)
    return url_for('static', filename=_DEFAULT_MALE)


def post_image_url(post):
    # ANTER: نفحص image_mime بدل image_data — يعمل حتى لو لم يُحمَّل الـ BLOB.
    if getattr(post, 'image_mime', None):
        return url_for('media.post_image_public', public_id=post.public_id)
    image = getattr(post, 'image', None)
    return _legacy_static_url(image) if image else ''
