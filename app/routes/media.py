from flask import Blueprint, Response, redirect, url_for

from app.models import Post, User

media_bp = Blueprint('media', __name__, url_prefix='/media')


def _image_response(data, mime_type):
    if not data:
        return redirect(url_for('static', filename='uploads/default.png'))
    return Response(
        data,
        mimetype=mime_type or 'image/png',
        headers={
            'Cache-Control': 'public, max-age=300',
            'Content-Length': str(len(data)),
        },
    )


@media_bp.route('/avatar/<int:user_id>')
def avatar(user_id):
    user = User.query.get_or_404(user_id)
    return _image_response(user.avatar_data, user.avatar_mime)


@media_bp.route('/post/<int:post_id>')
def post_image(post_id):
    post = Post.query.get_or_404(post_id)
    return _image_response(post.image_data, post.image_mime)
