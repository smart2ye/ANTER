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


@media_bp.route('/video/<public_id>')
def video_stream(public_id):
    """ANTER: بث فيديو الريل من قاعدة البيانات (تخزين دائم)."""
    from app.models import Video
    from flask import abort, Response, redirect, url_for

    video = Video.query.filter_by(public_id=public_id).first()
    if not video:
        abort(404)

    # إن وُجد BLOB في القاعدة → نُقدمه مباشرة
    if video.video_data:
        return Response(
            video.video_data,
            mimetype=video.video_mime or 'video/mp4',
            headers={
                'Content-Length': str(len(video.video_data)),
                'Accept-Ranges': 'bytes',
                'Cache-Control': 'public, max-age=3600',
            },
        )

    # fallback: الملف على القرص (للتوافق مع الملفات القديمة)
    if video.file_path:
        return redirect(url_for('static', filename='uploads/' + video.file_path))

    abort(404)


@media_bp.route('/video-thumb/<public_id>')
def video_thumbnail(public_id):
    """ANTER: الصورة المصغرة للريل من قاعدة البيانات."""
    from app.models import Video
    from flask import abort, Response, redirect, url_for

    video = Video.query.filter_by(public_id=public_id).first()
    if not video:
        abort(404)

    if video.thumbnail_data:
        return Response(
            video.thumbnail_data,
            mimetype=video.thumbnail_mime or 'image/jpeg',
            headers={
                'Content-Length': str(len(video.thumbnail_data)),
                'Cache-Control': 'public, max-age=3600',
            },
        )

    if video.thumbnail_path and video.thumbnail_path != 'default_thumb.png':
        return redirect(url_for('static', filename='uploads/' + video.thumbnail_path))

    abort(404)


@media_bp.route('/post/<int:post_id>')
def post_image(post_id):
    """Legacy numeric media URL for older rendered pages."""
    post = Post.query.get_or_404(post_id)
    return redirect(url_for('media.post_image_public', public_id=post.public_id), code=301)


@media_bp.route('/p/<public_id>')
def post_image_public(public_id):
    post = Post.query.filter_by(public_id=public_id).first_or_404()
    return _image_response(post.image_data, post.image_mime)
