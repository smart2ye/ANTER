from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify, session, abort
from flask import abort
from flask_login import login_required, current_user
from app import db, csrf
from app.models import Post, Comment, CommentLike, Like, Notification, User, Report, Repost, HiddenPost, Hashtag, post_hashtag, Video
from app.forms.post import PostForm
from app.utils.helpers import extract_hashtags, allowed_audio_file, verify_audio_magic, extract_link_metadata as extract_safe_link_metadata, log_user_activity, save_video_file, create_thumbnail, allowed_video_file
from app.utils.image_storage import prepare_image_data
from app.services.anter_user_messages import send_report_receipt
from app.services.privacy import POST_VISIBILITIES, can_view_post
from app.services.moment_detector import detect_for_post
from app.services.moderation import classify_post, should_hide, CATEGORY_LABELS
from app.models.moment import Moment, MomentPost

from datetime import datetime
import os
import secrets
import uuid

posts_bp = Blueprint('posts', __name__)

@posts_bp.route('/edit/<int:post_id>', methods=['GET', 'POST'])
@login_required
def edit(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author_id != current_user.id:
        flash('ليس لديك صلاحية تعديل هذا المنشور', 'danger')
        return redirect(url_for('main.index'))

    form = PostForm(obj=post)
    if form.validate_on_submit():
        content = form.content.data.strip()
        if not content:
            flash('المنشور لا يمكن أن يكون فارغاً', 'danger')
            return redirect(url_for('posts.edit', post_id=post_id))
        
        post.content = content
        visibility = request.form.get('visibility', post.visibility)
        post.visibility = visibility if visibility in POST_VISIBILITIES else post.visibility
        post.updated_at = datetime.utcnow()
        post.link_url, post.link_title, post.link_description, post.link_image = extract_safe_link_metadata(content)

        uploaded_image = form.image.data
        if uploaded_image and getattr(uploaded_image, 'filename', ''):
            image_data, image_mime = prepare_image_data(uploaded_image)
            if not image_data:
                flash('تعذر قراءة الصورة. استخدم JPG أو PNG أو GIF أو WEBP بحجم ضمن الحد المسموح.', 'danger')
                return redirect(url_for('posts.edit', post_id=post_id))
            post.image_data = image_data
            post.image_mime = image_mime

        # تحديث الوسوم عبر عناصر العلاقة الديناميكية، التي لا تدعم clear().
        for existing_tag in post.hashtags.all():
            post.hashtags.remove(existing_tag)
        hashtags = extract_hashtags(content)
        for tag_name in dict.fromkeys(hashtags):
            tag = Hashtag.query.filter_by(name=tag_name).first()
            if not tag:
                tag = Hashtag(name=tag_name)
                db.session.add(tag)
                db.session.flush()
            post.hashtags.append(tag)
        
        db.session.commit()
        log_user_activity(current_user.id, 'post_edit', {'post_id': post.id})
        flash('تم تحديث المنشور بنجاح!', 'success')
        return redirect(url_for('main.index'))
    
    return render_template('posts/edit.html', post=post, form=form)

@posts_bp.route('/delete/<int:post_id>', methods=['POST'])
@login_required
def delete(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author_id != current_user.id and not current_user.is_admin:
        flash('ليس لديك صلاحية حذف هذا المنشور', 'danger')
        return redirect(url_for('main.index'))
    
    deleted_post_id = post.id
    db.session.delete(post)
    db.session.commit()
    log_user_activity(current_user.id, 'post_delete', {'post_id': deleted_post_id})
    flash('تم حذف المنشور بنجاح!', 'success')
    return redirect(url_for('main.index'))

@posts_bp.route('/like/<int:post_id>', methods=['POST'])
@login_required
@csrf.exempt
def like(post_id):
    post = Post.query.get_or_404(post_id)
    if not can_view_post(current_user, post):
        abort(403)
    payload = request.get_json(silent=True) or {}
    reaction_type = payload.get('reaction', 'like')
    allowed_reactions = {'like', 'love', 'haha', 'angry', 'sad'}

    if reaction_type not in allowed_reactions:
        reaction_type = 'like'

    like = Like.query.filter_by(
        user_id=current_user.id,
        post_id=post_id
    ).first()

    if like:
        if like.reaction_type == reaction_type:
            db.session.delete(like)
            liked = False
        else:
            like.reaction_type = reaction_type
            liked = True
    else:
        like = Like(
            user_id=current_user.id,
            post_id=post_id,
            reaction_type=reaction_type
        )
        db.session.add(like)
        liked = True

        # ANTER: إشعار مجمّع — واحد لكل منشور، يُحدَّث عند كل إعجاب جديد.
        if post.author_id != current_user.id:
            import json as _json
            existing = Notification.query.filter_by(
                user_id=post.author_id,
                action='like',
                post_id=post_id,
            ).order_by(Notification.created_at.desc()).first()

            if existing is None:
                # لا يوجد إشعار سابق → أنشئ واحدًا.
                db.session.add(Notification(
                    user_id=post.author_id,
                    actor_id=current_user.id,
                    action='like',
                    post_id=post_id,
                    extra_text='[]',
                ))
            elif existing.actor_id != current_user.id:
                # يوجد إشعار سابق → أضف الحالي إلى القائمة، وحدّث التوقيت.
                try:
                    extras = _json.loads(existing.extra_text or '[]')
                    if not isinstance(extras, list):
                        extras = []
                except Exception:
                    extras = []
                if current_user.id not in extras:
                    extras.append(current_user.id)
                # ANTER: احفظ الـ actor السابق في القائمة قبل التحديث.
                if existing.actor_id != current_user.id:
                    if existing.actor_id not in extras:
                        extras.insert(0, existing.actor_id)
                    existing.actor_id = current_user.id
                existing.extra_text = _json.dumps(extras)
                existing.is_read = False
                existing.created_at = datetime.utcnow()

    db.session.commit()
    log_user_activity(
        current_user.id,
        'post_reaction_add' if liked else 'post_reaction_remove',
        {'post_id': post_id, 'reaction': reaction_type},
    )
    reaction_counts = {key: 0 for key in allowed_reactions}
    for stored_reaction in post.likes.all():
        reaction_counts[stored_reaction.reaction_type] = reaction_counts.get(stored_reaction.reaction_type, 0) + 1

    # آخر المتفاعلين — مع ضمان إدراج المستخدم الحالي إذا كان متفاعلاً
    all_reactions = list(
        Like.query
        .filter_by(post_id=post_id)
        .order_by(Like.created_at.desc(), Like.id.desc())
        .all()
    )

    current_reaction = next(
        (item for item in all_reactions if item.user_id == current_user.id),
        None
    )

    recent_reactions = []

    # المستخدم الحالي أولاً إذا كان لديه تفاعل
    if current_reaction:
        recent_reactions.append(current_reaction)

    # إضافة أحدث المتفاعلين الآخرين حتى يصل العدد إلى 3
    for item in all_reactions:
        if len(recent_reactions) >= 3:
            break
        if item.user_id == current_user.id:
            continue
        recent_reactions.append(item)

    recent_users = []
    seen_users = set()

    for item in recent_reactions:
        if item.user_id in seen_users:
            continue

        seen_users.add(item.user_id)

        user = User.query.get(item.user_id)
        if not user:
            continue
        # ANTER: لا نُظهر المتفاعلين المحذوفين.
        if getattr(user, 'is_deleted', False):
            continue

        # اختيار اسم العرض المتاح في نموذج المستخدم
        name = user.name or user.username or 'مستخدم'

        recent_users.append({
            'id': user.id,
            'name': name,
            'is_current_user': user.id == current_user.id
        })

    return jsonify({
        'liked': liked,
        'reaction': reaction_type if liked else None,
        'count': post.likes.count(),
        'reaction_counts': reaction_counts,
        'recent_users': recent_users
    })

@posts_bp.route('/post/<int:post_id>')
@login_required
def view(post_id):
    """Legacy numeric post URL; keep shared links working while moving to opaque IDs."""
    post = Post.query.get_or_404(post_id)
    if not can_view_post(current_user, post):
        abort(403)
    return redirect(url_for('posts.view_post', public_id=post.public_id), code=301)

@posts_bp.route('/wall/<username>', methods=['POST'])
@login_required
def post_on_wall(username):
    """نشر منشور نصي على حائط مستخدم آخر."""
    from app.services.privacy import can_post_on_wall

    wall_owner = User.query.filter_by(username=username).first_or_404()

    if not can_post_on_wall(current_user, wall_owner):
        flash('لا يمكنك الكتابة على حائط هذا المستخدم.', 'danger')
        return redirect(url_for('users.profile', username=username))

    content = (request.form.get('content') or '').strip()
    if not content:
        flash('لا يمكن نشر منشور فارغ.', 'warning')
        return redirect(url_for('users.profile', username=username))

    if len(content) > 3000:
        content = content[:3000]

    try:
        post = Post(
            content=content,
            author_id=current_user.id,
            wall_owner_id=wall_owner.id,
            visibility='public',
        )
        db.session.add(post)
        db.session.flush()

        # إشعار لصاحب الحائط
        if wall_owner.id != current_user.id:
            notif = Notification(
                user_id=wall_owner.id,
                actor_id=current_user.id,
                action='wall_post',
                post_id=post.id,
            )
            db.session.add(notif)

        db.session.commit()

        try:
            log_user_activity(current_user.id, 'wall_post', {
                'post_id': post.id,
                'wall_owner_id': wall_owner.id,
            })
        except Exception:
            pass

        flash('تم نشر المنشور على الحائط.', 'success')
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Failed to post on wall')
        flash('تعذر نشر المنشور. حاول مرة أخرى.', 'danger')

    return redirect(url_for('users.profile', username=username))


@posts_bp.route('/comment/<int:post_id>', methods=['POST'])
@login_required
@csrf.exempt
def comment(post_id):
    post = Post.query.get_or_404(post_id)
    if not can_view_post(current_user, post):
        abort(403)
    content = request.form.get('content', '').strip()
    parent_id = request.form.get('parent_id', type=int)
    
    uploaded_audio = request.files.get('audio')
    audio_url = None
    if uploaded_audio and uploaded_audio.filename:
        if allowed_audio_file(uploaded_audio.filename) and verify_audio_magic(uploaded_audio.stream):
            try:
                audio_bytes = uploaded_audio.read()
                max_size = current_app.config['MAX_AUDIO_MESSAGE_BYTES']
                if len(audio_bytes) <= max_size:
                    ext = uploaded_audio.filename.rsplit('.', 1)[1].lower()
                    filename = f"comment_{current_user.id}_{uuid.uuid4().hex[:8]}.{ext}"
                    upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'audio')
                    os.makedirs(upload_folder, exist_ok=True)
                    filepath = os.path.join(upload_folder, filename)
                    uploaded_audio.stream.seek(0)
                    uploaded_audio.save(filepath)
                    audio_url = f"/static/uploads/audio/{filename}"
                    if not content:
                        content = "🎤 تسجيل صوتي"
            except Exception:
                current_app.logger.exception('تعذر حفظ التعليق الصوتي')

    if not content and not audio_url:
        flash('التعليق لا يمكن أن يكون فارغاً', 'danger')
        return redirect(url_for('posts.view_post', public_id=post.public_id))
    
    comment = Comment(content=content, author_id=current_user.id, post_id=post_id, parent_id=parent_id, audio_url=audio_url)
    db.session.add(comment)
    db.session.flush()
    
    # معالجة الإشارات (@mention) — نظام موحّد
    from app.services.mentions import process_mentions
    reply_to_user_id = None
    if parent_id:
        pc = Comment.query.get(parent_id)
        if pc:
            reply_to_user_id = pc.author_id
    process_mentions(
        content,
        actor=current_user,
        post_id=post_id,
        comment_id=comment.id,
        reply_to_user_id=reply_to_user_id,
    )

    # إشعار لصاحب المنشور إذا لم يكن هو المعلق
    if post.author_id != current_user.id:
        notification = Notification(
            user_id=post.author_id,
            actor_id=current_user.id,
            action='comment',
            post_id=post_id,
        )
        db.session.add(notification)
        
    # إذا كان رداً على تعليق، نبه صاحب التعليق الأصلي
    if parent_id:
        parent_comment = Comment.query.get(parent_id)
        if parent_comment and parent_comment.author_id != current_user.id and parent_comment.author_id != post.author_id:
            reply_notif = Notification(
                user_id=parent_comment.author_id,
                actor_id=current_user.id,
                action='reply',
                post_id=post_id
            )
            db.session.add(reply_notif)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    log_user_activity(current_user.id, 'comment_create', {'post_id': post_id, 'comment_id': comment.id})
    
    flash('تم إضافة التعليق بنجاح!', 'success')
    return redirect(url_for('posts.view_post', public_id=post.public_id))

@posts_bp.route('/like_comment/<int:comment_id>', methods=['POST'])
@login_required
@csrf.exempt
def like_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    if not can_view_post(current_user, comment.post):
        abort(403)
    like = CommentLike.query.filter_by(user_id=current_user.id, comment_id=comment_id).first()
    
    if like:
        db.session.delete(like)
        liked = False
    else:
        like = CommentLike(user_id=current_user.id, comment_id=comment_id)
        db.session.add(like)
        liked = True
        
        # إشعار
        if comment.author_id != current_user.id:
            notification = Notification(
                user_id=comment.author_id,
                actor_id=current_user.id,
                action='like_comment',
                post_id=comment.post_id,
            )
            db.session.add(notification)
    
    db.session.commit()
    log_user_activity(
        current_user.id,
        'comment_reaction_add' if liked else 'comment_reaction_remove',
        {'comment_id': comment_id, 'post_id': comment.post_id},
    )
    return jsonify({'liked': liked, 'count': comment.likes.count()})

@posts_bp.route('/share-video/<int:video_id>', methods=['POST'])
@login_required
@csrf.exempt
def share_video(video_id):
    video = Video.query.filter_by(
        id=video_id,
        is_reel=True
    ).first_or_404()

    reel_url = url_for(
        'videos.watch',
        public_id=video.public_id
    )

    thumbnail_url = None
    if video.thumbnail_path:
        thumbnail_url = url_for(
            'static',
            filename='uploads/' + video.thumbnail_path
        )

    post = Post(
        content='شاهد هذا الريل على ANTER 🎬',
        author_id=current_user.id,
        visibility='public',
        link_url=reel_url,
        link_title=video.title or 'ريل جديد',
        link_description=video.description or '',
        link_image=thumbnail_url,
        shared_video_id=video.id,
    )

    db.session.add(post)

    video.shares = (video.shares or 0) + 1

    db.session.flush()

    detect_for_post(post)

    db.session.commit()

    log_user_activity(
        current_user.id,
        'video_share',
        {'video_id': video.id, 'post_id': post.id}
    )

    return jsonify({
        'success': True,
        'message': 'تمت مشاركة الريل داخل ANTER ✓',
        'post_id': post.id,
        'post_public_id': post.public_id,
        'share_count': video.shares,
    })


@posts_bp.route('/repost/<int:post_id>', methods=['POST'])
@login_required
@csrf.exempt
def repost(post_id):
    post = Post.query.get_or_404(post_id)
    if not can_view_post(current_user, post):
        abort(403)
    repost = Repost.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    
    if repost:
        db.session.delete(repost)
        reposted = False
    else:
        repost = Repost(user_id=current_user.id, post_id=post_id)
        db.session.add(repost)
        reposted = True
        
        # إشعار
        if post.author_id != current_user.id:
            notification = Notification(
                user_id=post.author_id,
                actor_id=current_user.id,
                action='repost',
                post_id=post_id,
            )
            db.session.add(notification)
    
    db.session.commit()
    log_user_activity(current_user.id, 'repost_add' if reposted else 'repost_remove', {'post_id': post_id})
    return jsonify({'reposted': reposted, 'count': post.reposts.count()})

@posts_bp.route('/report', methods=['POST'])
@posts_bp.route('/report/<int:post_id>', methods=['POST'])
@login_required
@csrf.exempt
def report(post_id=None):
    """Store a report and acknowledge it through the official assistant account."""
    payload = request.get_json(silent=True) or {}
    is_json_request = request.is_json or bool(payload)

    if post_id is None:
        post_id = payload.get('post_id')
    try:
        post_id = int(post_id)
    except (TypeError, ValueError):
        post_id = None

    reason = (payload.get('reason') if is_json_request else request.form.get('reason', '')).strip()
    details = (payload.get('details') if is_json_request else request.form.get('details', '')).strip()
    post = Post.query.get_or_404(post_id) if post_id else None
    if post and not can_view_post(current_user, post):
        abort(403)

    if not post or not reason:
        message = 'يرجى اختيار منشور وسبب واضح للبلاغ.'
        if is_json_request:
            return jsonify({'success': False, 'message': message}), 400
        flash(message, 'danger')
        return redirect(url_for('main.index'))

    # ANTER: لا يُسمح بالإبلاغ عن منشورك الخاص
    if post.author_id == current_user.id:
        message = 'لا يمكنك الإبلاغ عن منشورك الخاص.'
        if is_json_request:
            return jsonify({'success': False, 'message': message}), 400
        flash(message, 'warning')
        return redirect(url_for('posts.view_post', public_id=post.public_id))

    existing = Report.query.filter_by(reporter_id=current_user.id, post_id=post.id).first()
    if existing:
        message = 'لقد أرسلت بلاغاً سابقاً عن هذا المنشور.'
        if is_json_request:
            return jsonify({'success': False, 'message': message}), 409
        flash(message, 'warning')
        return redirect(url_for('posts.view_post', public_id=post.public_id))

    report = Report(
        reporter_id=current_user.id,
        post_id=post.id,
        reason=reason[:200],
        details=details[:2000],
        status='pending',
    )
    db.session.add(report)
    db.session.flush()

    # ANTER: مراقبة آلية — مساعد أنتر يقرأ المنشور ويُقرر
    moderation_triggered = False
    try:
        if (post.moderation_status or 'clean') == 'clean':
            cls = classify_post(
                content=post.content or '',
                report_reason=report.reason or '',
                report_details=report.details or '',
            )
            if should_hide(cls):
                post.moderation_status = 'under_review'
                post.moderation_reason = cls.get('reason') or CATEGORY_LABELS.get(cls.get('category', ''), 'مخالفة محتملة')
                post.moderation_at = datetime.utcnow()
                moderation_triggered = True
                # إشعار لصاحب المنشور
                db.session.add(Notification(
                    user_id=post.author_id,
                    actor_id=current_user.id,
                    action='content_under_review',
                    post_id=post.id,
                    extra_text=f'السبب: {post.moderation_reason}',
                ))
    except Exception:
        current_app.logger.exception('فشل التحليل الآلي للبلاغ (غير حرج)')

    send_report_receipt(current_user, report, post)
    db.session.commit()
    log_user_activity(current_user.id, 'report_create', {'post_id': post.id, 'auto_hidden': moderation_triggered})

    message = 'تم استلام البلاغ وإحالته للمراجعة البشرية.'
    if is_json_request:
        return jsonify({'success': True, 'message': message, 'report_id': report.id})
    flash(message, 'success')
    return redirect(url_for('posts.view_post', public_id=post.public_id))

@posts_bp.route('/p/<public_id>/appeal', methods=['POST'])
@login_required
def appeal_post(public_id):
    """صاحب المنشور يطعن على إزالة منشوره."""
    post = Post.query.filter_by(public_id=public_id).first_or_404()

    if post.author_id != current_user.id:
        flash('لا يمكنك الاعتراض على منشور ليس لك.', 'danger')
        return redirect(url_for('posts.view_post', public_id=public_id))

    if getattr(post, 'moderation_status', 'clean') != 'removed':
        flash('لا يمكن الاعتراض إلا على منشور تمت إزالته.', 'info')
        return redirect(url_for('posts.view_post', public_id=public_id))

    # منع الاعتراض المكرر
    existing = Report.query.filter_by(
        reporter_id=current_user.id,
        post_id=post.id,
        reason='content_appeal',
    ).first()
    if existing:
        flash('لديك اعتراض قيد المراجعة بالفعل على هذا المنشور.', 'info')
        return redirect(url_for('posts.view_post', public_id=public_id))

    details = (request.form.get('details') or '').strip()[:2000]

    db.session.add(Report(
        reporter_id=current_user.id,
        post_id=post.id,
        reason='content_appeal',
        details=details or 'اعتراض على قرار الإزالة (بلا تفاصيل).',
        status='pending',
    ))
    db.session.commit()

    flash('✅ تم استلام اعتراضك. سيراجعه فريق أنتر خلال 24-48 ساعة.', 'success')
    return redirect(url_for('posts.view_post', public_id=public_id))


@posts_bp.route('/hide/<int:post_id>', methods=['POST'])
@login_required
@csrf.exempt
def hide(post_id):
    post = Post.query.get_or_404(post_id)
    if not can_view_post(current_user, post):
        abort(403)
    
    hidden = HiddenPost.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    if not hidden:
        hidden = HiddenPost(user_id=current_user.id, post_id=post_id)
        db.session.add(hidden)
        db.session.commit()
        log_user_activity(current_user.id, 'post_hide', {'post_id': post_id})
    
    flash('تم إخفاء المنشور', 'info')
    return redirect(url_for('main.index'))



@posts_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    form = PostForm()

    if request.method == 'GET':
        return render_template('posts/create.html', form=form)

    # Composer الجديد يستخدم media، مع إبقاء image القديم متوافقًا مؤقتًا.
    uploaded_media = request.files.get('media')
    uploaded_image = request.files.get('image')

    content = request.form.get('content', '').strip()
    moment_id = request.args.get('moment_id', type=int)

    # إذا لم يوجد media، استخدم image القديم للتوافق مع الواجهة القديمة.
    media_file = uploaded_media if uploaded_media and getattr(uploaded_media, 'filename', '') else uploaded_image

    # ANTER: السماح بمنشور بلا نص إن كان هناك وسائط.
    _has_media = bool(media_file and getattr(media_file, 'filename', ''))
    if not content and not _has_media:
        flash('اكتب نصًا أو أضف صورة/فيديو.', 'danger')
        return redirect(url_for('posts.create'))

    image_data, image_mime = None, None
    video = None
    attachment_type = 'بدون مرفق'

    try:
        if media_file and getattr(media_file, 'filename', ''):
            filename = media_file.filename.lower()
            extension = filename.rsplit('.', 1)[1] if '.' in filename else ''

            # صورة
            if extension in {'jpg', 'jpeg', 'png', 'gif', 'webp'}:
                image_data, image_mime = prepare_image_data(media_file)
                if not image_data:
                    flash('تعذر قراءة الصورة. استخدم JPG أو PNG أو GIF أو WEBP بحجم ضمن الحد المسموح.', 'danger')
                    return redirect(url_for('posts.create'))
                attachment_type = 'صورة'

            # فيديو → Feed + Reel
            elif allowed_video_file(filename):
                try:
                    media_file.stream.seek(0, 2)
                    video_size = media_file.stream.tell()
                    media_file.stream.seek(0)
                except (AttributeError, OSError):
                    video_size = 0

                max_video_bytes = current_app.config['MAX_VIDEO_UPLOAD_BYTES']
                if video_size > max_video_bytes:
                    max_video_mb = max_video_bytes // (1024 * 1024)
                    flash(
                        f'حجم الفيديو أكبر من الحد المسموح ({max_video_mb} MB).',
                        'danger'
                    )
                    return redirect(url_for('posts.create'))

                video_path = save_video_file(media_file, is_reel=True)
                if not video_path:
                    flash('فشل في حفظ الفيديو. تأكد من الصيغة والحجم.', 'danger')
                    return redirect(url_for('posts.create'))

                thumbnail_path = create_thumbnail(video_path, is_reel=True)

                video = Video(
                    title=content[:200] or 'ريل جديد',
                    description=content,
                    file_path=video_path,
                    thumbnail_path=thumbnail_path or 'default_thumb.png',
                    is_reel=True,
                    author_id=current_user.id,
                )
                db.session.add(video)
                db.session.flush()

                attachment_type = 'فيديو + ريلز'

            else:
                flash('نوع الملف غير مدعوم. اختر صورة أو فيديو.', 'danger')
                return redirect(url_for('posts.create'))

        hashtags = extract_hashtags(content)
        link_url, link_title, link_desc, link_img = extract_safe_link_metadata(content)

        visibility = request.form.get('visibility', 'public')
        post = Post(
            content=content,
            author_id=current_user.id,
            visibility=visibility if visibility in POST_VISIBILITIES else 'public',
            image_data=image_data,
            image_mime=image_mime,
            shared_video_id=video.id if video else None,
            link_url=link_url,
            link_title=link_title,
            link_description=link_desc,
            link_image=link_img,
        )
        db.session.add(post)
        db.session.flush()

        moment = None
        if moment_id:
            moment = Moment.query.filter_by(
                id=moment_id,
                status='active'
            ).first()

        for tag_name in dict.fromkeys(hashtags):
            tag = Hashtag.query.filter_by(name=tag_name).first()
            if not tag:
                tag = Hashtag(name=tag_name)
                db.session.add(tag)
                db.session.flush()
            post.hashtags.append(tag)

        # ANTER: الميزات المساعدة (Moments + الإشارات) يجب ألّا تُفشل النشر.
        # نغلّفها بـ try/except منفصل، فحتى لو فشلت بسبب ضغط AI أو timeout،
        # يبقى المنشور محفوظًا ويُعاد المستخدم للرئيسية بنجاح.
        try:
            detect_for_post(post)

            if moment:
                db.session.add(
                    MomentPost(
                        moment_id=moment.id,
                        post_id=post.id,
                    )
                )
                moment.updated_at = datetime.utcnow()

            # نظام الإشارات الموحّد (منشورات)
            from app.services.mentions import process_mentions
            process_mentions(
                content,
                actor=current_user,
                post_id=post.id,
                comment_id=None,
                reply_to_user_id=None,
            )
        except Exception:
            current_app.logger.exception('Ancillary post features failed (non-fatal)')

        db.session.commit()

        try:
            log_user_activity(
                current_user.id,
                'post_create',
                {
                    'post_id': post.id,
                    'attachment': attachment_type,
                    'video_id': video.id if video else None,
                }
            )
        except Exception:
            current_app.logger.exception('log_user_activity failed (non-fatal)')

        flash('تم نشر المنشور بنجاح!', 'success')
        # ANTER: تمرير new=<id> لعرض المنشور في أعلى الـ feed مرة واحدة.
        return redirect(url_for('main.index', new=post.id))

    except Exception:
        db.session.rollback()
        current_app.logger.exception('Failed to create post from composer')
        flash('حدث خطأ أثناء نشر المنشور. حاول مرة أخرى.', 'danger')
        return redirect(url_for('posts.create'))

@posts_bp.route('/comments/<int:post_id>/fragment')
@login_required
def comments_fragment(post_id):
    """Return one post's comments only when the reader opens the discussion."""
    post = Post.query.get_or_404(post_id)
    if not can_view_post(current_user, post):
        abort(403)
    return render_template('comments.html', post=post)


@posts_bp.route('/p/<public_id>/stats')
def post_stats(public_id):
    """ANTER: إحصاءات منشور — JSON عام لأي زائر."""
    from sqlalchemy import func
    from app.models import Like, Comment, Repost

    post = Post.query.filter_by(public_id=public_id).first_or_404()
    if not can_view_post(current_user, post):
        abort(403)

    likes = db.session.query(func.count(Like.id)).filter_by(post_id=post.id).scalar() or 0
    comments = db.session.query(func.count(Comment.id)).filter_by(post_id=post.id).scalar() or 0
    reposts = db.session.query(func.count(Repost.id)).filter_by(post_id=post.id).scalar() or 0

    return jsonify({
        'views': post.views or 0,
        'likes': likes,
        'comments': comments,
        'reposts': reposts,
        'shares': reposts,
        'total_engagement': likes + comments + reposts,
        'is_verified_author': bool(getattr(post.author, 'is_verified', False)),
    })

@posts_bp.route('/p/<public_id>')
def view_post(public_id):
    post = Post.query.filter_by(public_id=public_id).first_or_404()
    if not can_view_post(current_user, post):
        abort(403)

    # ANTER: عدّاد مشاهدات — مرة واحدة لكل جلسة لكل منشور.
    try:
        from flask import session as _session
        seen_key = 'viewed_posts'
        seen = _session.get(seen_key) or []
        if post.id not in seen:
            db.session.query(Post).filter_by(id=post.id).update(
                {Post.views: Post.views + 1}, synchronize_session=False
            )
            db.session.commit()
            seen = (seen + [post.id])[-200:]  # حد 200 لمنع تضخم الجلسة
            _session[seen_key] = seen
    except Exception:
        db.session.rollback()

    return render_template('post_detail.html', post=post)

# ============================================================
# ANTER: تعديل تعليق
# ============================================================
@posts_bp.route('/comment/<int:comment_id>/edit', methods=['POST'])
@login_required
@csrf.exempt
def edit_comment(comment_id):
    """يسمح لصاحب التعليق فقط بتعديله، ويحدّث edited_at."""
    comment = Comment.query.get_or_404(comment_id)

    if comment.author_id != current_user.id:
        return jsonify({'success': False, 'message': 'لا يمكنك تعديل تعليق غيرك.'}), 403

    data = request.get_json(silent=True) or request.form
    content = (data.get('content') or '').strip()

    if not content:
        return jsonify({'success': False, 'message': 'التعليق لا يمكن أن يكون فارغاً.'}), 400
    if len(content) > 2000:
        return jsonify({'success': False, 'message': 'التعليق طويل جداً (الحد 2000 حرف).'}), 400

    # إذا لم يتغير المحتوى → لا نُحدّث edited_at
    if content == comment.content:
        return jsonify({
            'success': True,
            'message': 'لم يتم أي تغيير.',
            'content': comment.content,
            'edited': bool(comment.edited_at),
        })

    comment.content = content
    comment.edited_at = datetime.utcnow()
    db.session.commit()

    log_user_activity(current_user.id, 'comment_edit', {
        'post_id': comment.post_id,
        'comment_id': comment.id,
    })

    return jsonify({
        'success': True,
        'message': 'تم تعديل التعليق.',
        'content': comment.content,
        'edited': True,
    })


# ============================================================
# ANTER: حذف تعليق
# ============================================================
@posts_bp.route('/comment/<int:comment_id>/delete', methods=['POST'])
@login_required
@csrf.exempt
def delete_comment(comment_id):
    """يسمح لصاحب التعليق (أو الأدمن أو صاحب المنشور) بحذف التعليق."""
    comment = Comment.query.get_or_404(comment_id)
    post = Post.query.get(comment.post_id)

    can_delete = (
        comment.author_id == current_user.id
        or (post and post.author_id == current_user.id)
        or getattr(current_user, 'is_admin', False)
    )

    if not can_delete:
        return jsonify({'success': False, 'message': 'لا يمكنك حذف هذا التعليق.'}), 403

    post_id = comment.post_id
    comment_id_value = comment.id
    # الردود تُحذف تلقائيًا (cascade) بحسب تعريف العلاقة
    db.session.delete(comment)
    db.session.commit()

    log_user_activity(current_user.id, 'comment_delete', {
        'post_id': post_id,
        'comment_id': comment_id_value,
    })

    return jsonify({
        'success': True,
        'message': 'تم حذف التعليق.',
        'comment_id': comment_id_value,
    })

