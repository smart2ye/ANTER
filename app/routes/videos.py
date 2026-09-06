from flask import Blueprint, current_app, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
from app.extensions import db, csrf
from app.models import Video, VideoLike, VideoComment, VideoCommentLike, Notification
from app.utils.helpers import save_video_file, create_thumbnail, log_user_activity

videos_bp = Blueprint('videos', __name__, url_prefix='/videos')

@videos_bp.route('/reels')
@login_required
def reels():
    videos = Video.query.filter_by(is_reel=True).order_by(Video.created_at.desc()).all()
    return render_template('videos/reels.html', videos=videos)

@videos_bp.route('/upload', methods=['GET', 'POST'])
@login_required
@csrf.exempt
def upload():
    if request.method == 'POST':
        description = request.form.get('description', '').strip()
        if not description:
            description = "فيديو جديد"
        is_reel = request.form.get('is_reel') == 'on'
        video_file = request.files.get('video')
        thumbnail_file = request.files.get('thumbnail')

        if not video_file or not video_file.filename:
            flash('الرجاء اختيار فيديو.', 'danger')
            return redirect(url_for('videos.upload'))

        # Reject an oversized video before copying it to permanent storage.
        # The request-level limit also allows a small multipart overhead and optional thumbnail.
        try:
            video_file.stream.seek(0, 2)
            video_size = video_file.stream.tell()
            video_file.stream.seek(0)
        except (AttributeError, OSError):
            video_size = 0

        max_video_bytes = current_app.config['MAX_VIDEO_UPLOAD_BYTES']
        if video_size > max_video_bytes:
            max_video_mb = max_video_bytes // (1024 * 1024)
            flash(f'حجم فيديو الريلز أكبر من الحد المسموح ({max_video_mb} MB). اضغط الفيديو ثم أعد المحاولة.', 'danger')
            return redirect(url_for('videos.upload'))

        video_path = save_video_file(video_file, is_reel)
        if not video_path:
            flash('فشل في حفظ الفيديو. تأكد من الصيغة والحجم.', 'danger')
            return redirect(url_for('videos.upload'))

        thumbnail_path = ''
        if thumbnail_file and thumbnail_file.filename:
            from app.utils.helpers import save_uploaded_image
            thumbnail_path = save_uploaded_image(thumbnail_file, 'thumbnails')
        else:
            thumbnail_path = create_thumbnail(video_path, is_reel)

        video = Video(
            title=description,
            description=description,
            file_path=video_path,
            thumbnail_path=thumbnail_path or 'default_thumb.png',
            is_reel=is_reel,
            author_id=current_user.id
        )
        db.session.add(video)
        db.session.commit()
        log_user_activity(current_user.id, 'video_upload', {'video_id': video.id, 'attachment': 'ريلز' if is_reel else 'فيديو'})

        flash('تم رفع الفيديو بنجاح!', 'success')
        return redirect(url_for('videos.reels' if is_reel else 'videos.watch', public_id=video.public_id))

    return render_template('videos/upload.html')

@videos_bp.route('/view/<public_id>', methods=['POST'])
@login_required
@csrf.exempt
def register_view(public_id):
    """تسجيل مشاهدة الريل مرة واحدة لكل جلسة."""
    video = Video.query.filter_by(public_id=public_id, is_reel=True).first_or_404()

    viewed_key = f'reel_viewed_{video.id}'

    if not session.get(viewed_key):
        video.views = (video.views or 0) + 1
        session[viewed_key] = True
        db.session.commit()

    return jsonify({
        'success': True,
        'views': video.views
    })


@videos_bp.route('/watch/<int:video_id>')
@login_required
def watch_legacy(video_id):
    """Legacy numeric video URL retained for existing shared links."""
    video = Video.query.get_or_404(video_id)
    return redirect(url_for('videos.watch', public_id=video.public_id), code=301)


@videos_bp.route('/r/<public_id>')
@login_required
def watch(public_id):
    video = Video.query.filter_by(public_id=public_id).first_or_404()
    video.views += 1
    db.session.commit()
    comments = video.comments.filter_by(parent_id=None).order_by(VideoComment.created_at.asc()).all()
    return render_template('videos/watch.html', video=video, comments=comments)

@videos_bp.route('/like/<int:video_id>', methods=['POST'])
@login_required
@csrf.exempt
def like(video_id):
    video = Video.query.get_or_404(video_id)
    like = VideoLike.query.filter_by(video_id=video_id, user_id=current_user.id).first()
    if like:
        db.session.delete(like)
        liked = False
    else:
        like = VideoLike(video_id=video_id, user_id=current_user.id)
        db.session.add(like)
        liked = True
        if video.author_id != current_user.id:
            notif = Notification(user_id=video.author_id, actor_id=current_user.id, action='like_video')
            db.session.add(notif)
    db.session.commit()
    log_user_activity(current_user.id, 'video_reaction_add' if liked else 'video_reaction_remove', {'video_id': video_id})
    return jsonify({'liked': liked, 'count': video.like_count()})

@videos_bp.route('/comments/<int:video_id>', methods=['GET'])
@login_required
def get_comments(video_id):
    """جلب تعليقات الريل وردهوده بصيغة JSON للـReels Bottom Sheet."""
    video = Video.query.get_or_404(video_id)

    comments = (
        video.comments
        .filter_by(parent_id=None)
        .order_by(VideoComment.created_at.desc())
        .limit(100)
        .all()
    )

    def serialize(comment):
        replies = (
            comment.replies
            .order_by(VideoComment.created_at.asc())
            .limit(50)
            .all()
        )

        return {
            'id': comment.id,
            'content': comment.content,
            'created_at': comment.created_at.isoformat() if comment.created_at else '',
            'likes': comment.like_count(),
            'liked': comment.likes.filter_by(user_id=current_user.id).first() is not None,
            'author': {
                'id': comment.author.id,
                'name': comment.author.name,
                'username': comment.author.username,
                'avatar': comment.author.avatar
            },
            'replies': [
                {
                    'id': reply.id,
                    'content': reply.content,
                    'created_at': reply.created_at.isoformat() if reply.created_at else '',
                    'likes': reply.like_count(),
                    'liked': reply.likes.filter_by(user_id=current_user.id).first() is not None,
                    'author': {
                        'id': reply.author.id,
                        'name': reply.author.name,
                        'username': reply.author.username,
                        'avatar': reply.author.avatar
                    }
                }
                for reply in replies
            ]
        }

    return jsonify({
        'success': True,
        'video_id': video.id,
        'count': video.comment_count(),
        'comments': [serialize(comment) for comment in comments]
    })


@videos_bp.route('/comment/<int:video_id>', methods=['POST'])
@login_required
@csrf.exempt
def comment(video_id):
    video = Video.query.get_or_404(video_id)
    content = request.form.get('content', '').strip()
    parent_id = request.form.get('parent_id', type=int)
    if not content:
        flash('التعليق لا يمكن أن يكون فارغاً.', 'danger')
        return redirect(url_for('videos.watch', public_id=video.public_id))

    comment = VideoComment(content=content, author_id=current_user.id, video_id=video.id)
    if parent_id:
        comment.parent_id = parent_id
        parent_comment = VideoComment.query.get(parent_id)
        if parent_comment and parent_comment.author_id != current_user.id:
            notif = Notification(user_id=parent_comment.author_id, actor_id=current_user.id, action='reply_video')
            db.session.add(notif)
    else:
        if video.author_id != current_user.id:
            notif = Notification(user_id=video.author_id, actor_id=current_user.id, action='comment_video')
            db.session.add(notif)

    db.session.add(comment)
    db.session.commit()
    log_user_activity(current_user.id, 'video_comment_create', {'video_id': video.id, 'comment_id': comment.id})
    # طلبات Reels AJAX تحصل على النتيجة مباشرة دون إعادة تحميل الصفحة.
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
        return jsonify({
            'success': True,
            'comment': {
                'id': comment.id,
                'content': comment.content,
                'created_at': comment.created_at.isoformat() if comment.created_at else '',
                'likes': 0,
                'liked': False,
                'author': {
                    'id': current_user.id,
                    'name': current_user.name,
                    'username': current_user.username,
                    'avatar': current_user.avatar
                }
            },
            'count': video.comment_count()
        })

    flash('تم إضافة التعليق.', 'success')
    return redirect(url_for('videos.watch', public_id=video.public_id))

@videos_bp.route('/like_comment/<int:comment_id>', methods=['POST'])
@login_required
@csrf.exempt
def like_comment(comment_id):
    comment = VideoComment.query.get_or_404(comment_id)
    like = VideoCommentLike.query.filter_by(comment_id=comment_id, user_id=current_user.id).first()
    if like:
        db.session.delete(like)
        liked = False
    else:
        like = VideoCommentLike(comment_id=comment_id, user_id=current_user.id)
        db.session.add(like)
        liked = True
    db.session.commit()
    log_user_activity(current_user.id, 'video_comment_reaction_add' if liked else 'video_comment_reaction_remove', {'comment_id': comment_id, 'video_id': comment.video_id})
    return jsonify({'liked': liked, 'count': comment.like_count()})
