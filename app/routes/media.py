from flask import Blueprint, Response, redirect, url_for

from app.models import Post, User

media_bp = Blueprint('media', __name__, url_prefix='/media')


def _image_response(data, mime_type):
    if not data:
        return redirect(url_for('static', filename='uploads/default.png'))

    # ETag بسيط من حجم البيانات — يتغير تلقائيًا عند تبديل الصورة.
    # مع 'no-cache, must-revalidate'، يسأل المتصفح السيرفر في كل مرة،
    # فيرد 304 بسرعة إن لم تتغير الصورة، أو الصورة الجديدة إن تغيّرت.
    etag = '"%d-%d"' % (len(data), hash(data[:512]) & 0xffffffff)

    return Response(
        data,
        mimetype=mime_type or 'image/png',
        headers={
            'Cache-Control': 'no-cache, must-revalidate',
            'ETag': etag,
            'Content-Length': str(len(data)),
        },
    )


@media_bp.route('/avatar/<int:user_id>')
def avatar(user_id):
    user = User.query.get_or_404(user_id)
    return _image_response(user.avatar_data, user.avatar_mime)


@media_bp.route('/post/<int:post_id>')
def post_image(post_id):
    """Legacy numeric media URL for older rendered pages."""
    post = Post.query.get_or_404(post_id)
    return redirect(url_for('media.post_image_public', public_id=post.public_id), code=301)


@media_bp.route('/p/<public_id>')
def post_image_public(public_id):
    post = Post.query.filter_by(public_id=public_id).first_or_404()
    return _image_response(post.image_data, post.image_mime)
