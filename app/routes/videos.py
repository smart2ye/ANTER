from flask import Blueprint, current_app, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
from app.extensions import db, csrf
from app.models import Video, VideoLike, VideoComment, VideoCommentLike, Notification, Report, Follow, UserBlock, User
from app.utils.helpers import save_video_file, create_thumbnail, log_user_activity
from app.utils.media_urls import avatar_url

videos_bp = Blueprint('videos', __name__, url_prefix='/videos')

@videos_bp.route('/reels')
@login_required
def reels():
    videos = Video.query.filter_by(is_reel=True).order_by(Video.created_at.desc()).all()

    # قائمة الأشخاص الذين يتابعهم المستخدم لإرسال الريلز إليهم.
    # لا تعتمد على حالة الاتصال: تشمل Online وOffline.
    blocked_ids = {
        row.blocked_id
        for row in UserBlock.query.filter_by(blocker_id=current_user.id).all()
    }
    blocked_ids.update(
        row.blocker_id
        for row in UserBlock.query.filter_by(blocked_id=current_user.id).all()
    )

    followed_users = (
        Follow.query
        .filter_by(follower_id=current_user.id)
        .all()
    )

    share_users = []
    followed_ids = {
        row.followed_id
        for row in followed_users
        if row.followed_id != current_user.id
        and row.followed_id not in blocked_ids
    }

    if followed_ids:
        share_users = (
            User.query
            .filter(User.id.in_(followed_ids))
            .order_by(User.name.asc(), User.username.asc())
            .all()
        )

    return render_template(
        'videos/reels.html',
        videos=videos,
        share_users=share_users,
    )

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

        # ANTER: نقرأ الملفات من القرص ونحفظها في قاعدة البيانات (تخزين دائم)
        video_bytes = None
        thumb_bytes = None

        try:
            from pathlib import Path
            uploads_root = Path(current_app.root_path) / 'static' / 'uploads'
            disk_video = uploads_root / video_path
            if disk_video.exists():
                video_bytes = disk_video.read_bytes()
        except Exception as e:
            current_app.logger.warning(f'تعذر قراءة الفيديو من القرص: {e}')

        try:
            if thumbnail_path and thumbnail_path != 'default_thumb.png':
                from pathlib import Path
                uploads_root = Path(current_app.root_path) / 'static' / 'uploads'
                disk_thumb = uploads_root / thumbnail_path
                if disk_thumb.exists():
                    thumb_bytes = disk_thumb.read_bytes()
        except Exception as e:
            current_app.logger.warning(f'تعذر قراءة الصورة المصغرة: {e}')

        # تحديد mime الصحيح
        video_ext = (video_path or '').rsplit('.', 1)[-1].lower()
        video_mime = {'mp4': 'video/mp4', 'webm': 'video/webm', 'mov': 'video/quicktime', 'avi': 'video/x-msvideo', 'mkv': 'video/x-matroska'}.get(video_ext, 'video/mp4')

        thumb_ext = (thumbnail_path or '').rsplit('.', 1)[-1].lower()
        thumb_mime = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'webp': 'image/webp', 'gif': 'image/gif'}.get(thumb_ext, 'image/jpeg')

        video = Video(
            title=description,
            description=description,
            file_path=video_path,
            thumbnail_path=thumbnail_path or 'default_thumb.png',
            is_reel=is_reel,
            author_id=current_user.id,
            video_data=video_bytes,
            video_mime=video_mime,
            thumbnail_data=thumb_bytes,
            thumbnail_mime=thumb_mime if thumb_bytes else None,
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

    # ANTER: بعد الريل المضغوط، نكمل بنفس خوارزمية reels_ranker
    # حتى تكون تجربة Reels موحّدة بين /videos/reels و /videos/r/<id>.
    try:
        from app.services.reels_ranker import rank_reels
        ranked = rank_reels(
            current_user,
            limit=20,
            exclude_ids=[video.id],
        )
        stream_videos = [video] + list(ranked)
    except Exception:
        stream_videos = [video]

    comments = video.comments.filter_by(parent_id=None).order_by(VideoComment.created_at.asc()).all()
    return render_template('videos/reels.html', videos=stream_videos, comments=comments)

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

@videos_bp.route('/report/<int:video_id>', methods=['POST'])
@login_required
@csrf.exempt
def report_video(video_id):
    """إنشاء بلاغ عن ريلز مع منع البلاغات المكررة."""
    video = Video.query.filter_by(id=video_id, is_reel=True).first_or_404()

    if video.author_id == current_user.id:
        return jsonify({
            'success': False,
            'message': 'لا يمكنك الإبلاغ عن ريلزك الخاص.'
        }), 400

    existing = Report.query.filter_by(
        reporter_id=current_user.id,
        video_id=video.id
    ).first()

    if existing is not None:
        return jsonify({
            'success': False,
            'message': 'لقد أرسلت بلاغاً عن هذا الريل مسبقاً.',
            'report_id': existing.id
        }), 409

    data = request.get_json(silent=True) or request.form
    reason = (data.get('reason') or '').strip()
    details = (data.get('details') or '').strip()

    allowed_reasons = {
        'spam': 'محتوى مزعج أو ترويجي',
        'harassment': 'تنمر أو مضايقة',
        'violence': 'عنف أو محتوى خطير',
        'sexual': 'محتوى جنسي',
        'hate': 'كراهية أو تحريض',
        'misinformation': 'معلومات مضللة',
        'copyright': 'انتهاك حقوق النشر',
        'other': 'سبب آخر',
    }

    if reason not in allowed_reasons:
        return jsonify({
            'success': False,
            'message': 'سبب البلاغ غير صالح.'
        }), 400

    report = Report(
        reporter_id=current_user.id,
        video_id=video.id,
        reason=allowed_reasons[reason],
        details=details[:2000],
    )

    db.session.add(report)
    log_user_activity(
        current_user.id,
        'video_report',
        {'video_id': video.id, 'reason': allowed_reasons[reason]}
    )
    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'تم استلام بلاغك وسيتم مراجعته من فريق ANTER.',
        'report_id': report.id
    })


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
            'edited_at': comment.edited_at.isoformat() if comment.edited_at else None,
            'author_id': comment.author_id,
            'can_edit': comment.author_id == current_user.id,
            'likes': comment.like_count(),
            'liked': comment.likes.filter_by(user_id=current_user.id).first() is not None,
            'author': {
                'id': comment.author.id,
                'name': comment.author.name,
                'username': comment.author.username,
                'avatar': comment.author.avatar,
                'avatar_url': avatar_url(comment.author)
            },
            'replies': [
                {
                    'id': reply.id,
                    'content': reply.content,
                    'created_at': reply.created_at.isoformat() if reply.created_at else '',
                    'edited_at': reply.edited_at.isoformat() if reply.edited_at else None,
                    'author_id': reply.author_id,
                    'can_edit': reply.author_id == current_user.id,
                    'likes': reply.like_count(),
                    'liked': reply.likes.filter_by(user_id=current_user.id).first() is not None,
                    'author': {
                        'id': reply.author.id,
                        'name': reply.author.name,
                        'username': reply.author.username,
                        'avatar': reply.author.avatar,
                        'avatar_url': avatar_url(reply.author)
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


@videos_bp.route('/comment/<int:comment_id>/edit', methods=['POST'])
@login_required
@csrf.exempt
def edit_video_comment(comment_id):
    """تعديل تعليق ريل — لصاحبه فقط."""
    c = VideoComment.query.get_or_404(comment_id)

    if c.author_id != current_user.id:
        return jsonify({'success': False, 'message': 'لا يمكنك تعديل تعليق غيرك.'}), 403

    data = request.get_json(silent=True) or request.form
    content = (data.get('content') or '').strip()

    if not content:
        return jsonify({'success': False, 'message': 'التعليق لا يمكن أن يكون فارغاً.'}), 400
    if len(content) > 2000:
        return jsonify({'success': False, 'message': 'التعليق طويل جداً.'}), 400

    if content == c.content:
        return jsonify({
            'success': True,
            'message': 'لم يتم أي تغيير.',
            'content': c.content,
            'edited': bool(c.edited_at),
        })

    c.content = content
    c.edited_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'تم تعديل التعليق.',
        'content': c.content,
        'edited': True,
    })


@videos_bp.route('/delete/<int:video_id>', methods=['POST'])
@login_required
@csrf.exempt
def delete_video(video_id):
    """حذف ريل — لصاحبه أو الأدمن."""
    video = Video.query.get_or_404(video_id)

    can_delete = (
        video.author_id == current_user.id
        or getattr(current_user, 'is_admin', False)
    )

    if not can_delete:
        return jsonify({'success': False, 'message': 'لا يمكنك حذف هذا الريل.'}), 403

    db.session.delete(video)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'تم حذف الريل.',
        'video_id': video_id,
    })


@videos_bp.route('/comment/<int:comment_id>/delete', methods=['POST'])
@login_required
@csrf.exempt
def delete_video_comment(comment_id):
    """حذف تعليق ريل — لصاحبه أو صاحب الريل أو الأدمن."""
    c = VideoComment.query.get_or_404(comment_id)
    video = Video.query.get(c.video_id)

    can_delete = (
        c.author_id == current_user.id
        or (video and video.author_id == current_user.id)
        or getattr(current_user, 'is_admin', False)
    )

    if not can_delete:
        return jsonify({'success': False, 'message': 'لا يمكنك حذف هذا التعليق.'}), 403

    video_id = c.video_id
    comment_id_value = c.id
    db.session.delete(c)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'تم حذف التعليق.',
        'comment_id': comment_id_value,
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
