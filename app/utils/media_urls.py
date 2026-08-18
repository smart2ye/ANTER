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


def avatar_url(user):
    if getattr(user, 'avatar_data', None):
        return url_for('media.avatar', user_id=user.id)
    return _legacy_static_url(getattr(user, 'avatar', None) or 'default.png')


def post_image_url(post):
    if getattr(post, 'image_data', None):
        return url_for('media.post_image_public', public_id=post.public_id)
    image = getattr(post, 'image', None)
    return _legacy_static_url(image) if image else ''
