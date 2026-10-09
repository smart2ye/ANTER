import os

from flask import (Blueprint, Response, current_app, redirect,
                    send_from_directory, url_for)

from app.models import Post, User

media_bp = Blueprint('media', __name__, url_prefix='/media')


def _image_response(data, mime_type, cache_seconds=300):
    if not data:
        return redirect(url_for('static', filename='uploads/default.png'))

    # ETag بسيط من حجم البيانات — يتغير تلقائيًا عند تبديل الصورة.
    etag = '"%d-%d"' % (len(data), hash(data[:512]) & 0xffffffff)

    cache_header = f'public, max-age={cache_seconds}'
    if cache_seconds >= 31536000:
        cache_header += ', immutable'

    return Response(
        data,
        mimetype=mime_type or 'image/png',
        headers={
            'Cache-Control': cache_header,
            'ETag': etag,
            'Content-Length': str(len(data)),
        },
    )


@media_bp.route('/avatar/<int:user_id>')
def avatar(user_id):
    user = User.query.get_or_404(user_id)
    if user.avatar_data:
        return _image_response(user.avatar_data, user.avatar_mime)
    # لا توجد صورة مرفوعة → استخدم أيقونة الذكر/الأنثى من static/img/
    legacy = user.avatar or ''
    if legacy.startswith('img/'):
        return send_from_directory(
            os.path.join(current_app.static_folder, 'img'),
            os.path.basename(legacy),
            mimetype='image/png',
            max_age=300,
        )
    return redirect(url_for('static', filename='uploads/default.png'))


# ANTER: الحد الأقصى لكل chunk عند بث الفيديو (2 MB).
# يمنع تحميل ملف 14 MB كاملًا في طلب واحد → يحل OOM على Render Free.
_VIDEO_CHUNK_SIZE = 2 * 1024 * 1024


def _fetch_video_chunk(public_id, start, length):
    """يجلب جزءًا من video_data من القاعدة دون تحميل BLOB كاملًا."""
    from sqlalchemy import text
    from app.extensions import db

    dialect = db.engine.dialect.name
    if dialect == 'postgresql':
        sql = text(
            "SELECT substring(video_data FROM :start FOR :length) "
            "FROM videos WHERE public_id = :pid"
        )
    else:
        sql = text(
            "SELECT substr(video_data, :start, :length) "
            "FROM videos WHERE public_id = :pid"
        )
    row = db.session.execute(
        sql, {"start": start + 1, "length": length, "pid": public_id}
    ).first()
    if not row or row[0] is None:
        return b''
    return bytes(row[0])


def _fetch_video_meta(public_id):
    """يجلب طول الفيديو ونوعه فقط — بدون BLOB."""
    from sqlalchemy import text
    from app.extensions import db

    row = db.session.execute(
        text(
            "SELECT length(video_data) AS size, video_mime, file_path "
            "FROM videos WHERE public_id = :pid"
        ),
        {"pid": public_id},
    ).first()
    return row


@media_bp.route('/video/<public_id>')
def video_stream(public_id):
    """ANTER: بث فيديو الريل على شكل chunks مع دعم Range requests.

    يمنع تحميل BLOB كاملًا في الذاكرة → لا OOM على Render Free Tier.
    """
    from flask import abort, Response, redirect, url_for, request

    meta = _fetch_video_meta(public_id)
    if meta is None:
        abort(404)

    total_size = int(meta.size) if meta.size is not None else 0
    mime = meta.video_mime or 'video/mp4'
    file_path = meta.file_path

    # fallback: الفيديو على القرص فقط (بدون BLOB)
    if total_size == 0:
        if file_path:
            return redirect(url_for('static', filename='uploads/' + file_path))
        abort(404)

    # -------- معالجة Range header --------
    range_header = request.headers.get('Range', '').strip()
    start = 0
    end = total_size - 1
    status = 200

    if range_header.startswith('bytes='):
        raw = range_header[6:]
        try:
            parts = raw.split(',', 1)[0].split('-', 1)
            if parts[0]:
                start = int(parts[0])
                if len(parts) > 1 and parts[1]:
                    end = int(parts[1])
            elif len(parts) > 1 and parts[1]:
                # "bytes=-N" = آخر N بايت
                tail = int(parts[1])
                start = max(0, total_size - tail)
                end = total_size - 1
        except (ValueError, IndexError):
            start, end = 0, total_size - 1

        if start < 0:
            start = 0
        if end >= total_size:
            end = total_size - 1
        if start > end:
            return Response(
                status=416,
                headers={'Content-Range': f'bytes */{total_size}'},
            )
        status = 206

    # -------- تقييد الحجم لكل طلب --------
    requested = end - start + 1
    if requested > _VIDEO_CHUNK_SIZE:
        end = start + _VIDEO_CHUNK_SIZE - 1
        content_length = _VIDEO_CHUNK_SIZE
    else:
        content_length = requested

    data = _fetch_video_chunk(public_id, start, content_length)

    headers = {
        'Content-Type': mime,
        'Content-Length': str(len(data)),
        'Accept-Ranges': 'bytes',
        'Cache-Control': 'public, max-age=3600',
    }
    if status == 206:
        headers['Content-Range'] = f'bytes {start}-{end}/{total_size}'

    return Response(data, status=status, headers=headers)


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
    # ANTER: public_id فريد ولا يتغير → cache سنة كاملة + immutable.
    return _image_response(
        post.image_data,
        post.image_mime,
        cache_seconds=31536000,
    )
