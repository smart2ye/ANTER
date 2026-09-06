from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify, session, abort
from flask import abort
from flask_login import login_required, current_user
from app import db, csrf
from app.models import Post, Comment, CommentLike, Like, Notification, User, Report, Repost, HiddenPost, Hashtag, post_hashtag
from app.forms.post import PostForm
from app.utils.helpers import extract_hashtags, allowed_audio_file, extract_link_metadata as extract_safe_link_metadata, log_user_activity
from app.utils.image_storage import prepare_image_data
from app.services.anter_user_messages import send_report_receipt
from app.services.privacy import POST_VISIBILITIES, can_view_post
from app.services.moment_detector import detect_for_post

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
        for tag_name in hashtags:
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

        # إشعار
        if post.author_id != current_user.id:
            notification = Notification(
                user_id=post.author_id,
                actor_id=current_user.id,
                action='like',
                post_id=post_id,
            )
            db.session.add(notification)

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
        if allowed_audio_file(uploaded_audio.filename):
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
    
    # معالجة الإشارات (@mention)
    from app.utils.helpers import parse_mentions
    import re
    usernames = re.findall(r'@([\w.]+)', content)
    for username in usernames:
        mentioned_user = User.query.filter_by(username=username).first()
        if mentioned_user and mentioned_user.id != current_user.id:
            notif = Notification(
                user_id=mentioned_user.id,
                actor_id=current_user.id,
                action='mention',
                post_id=post_id
            )
            db.session.add(notif)

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
    send_report_receipt(current_user, report, post)
    db.session.commit()
    log_user_activity(current_user.id, 'report_create', {'post_id': post.id})

    message = 'تم استلام البلاغ وإحالته للمراجعة البشرية.'
    if is_json_request:
        return jsonify({'success': True, 'message': message, 'report_id': report.id})
    flash(message, 'success')
    return redirect(url_for('posts.view_post', public_id=post.public_id))

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
    if form.validate_on_submit():
        content = form.content.data
        if not content:
            flash('المنشور لا يمكن أن يكون فارغاً', 'danger')
            return redirect(url_for('posts.create'))

        hashtags = extract_hashtags(content)
        link_url, link_title, link_desc, link_img = extract_safe_link_metadata(content)

        # تخزين الصورة داخل قاعدة البيانات الدائمة عند إرفاقها بالمنشور.
        uploaded_image = form.image.data
        image_data, image_mime = (None, None)
        if uploaded_image and getattr(uploaded_image, 'filename', ''):
            image_data, image_mime = prepare_image_data(uploaded_image)
            if not image_data:
                flash('تعذر قراءة الصورة. استخدم JPG أو PNG أو GIF أو WEBP بحجم ضمن الحد المسموح.', 'danger')
                return redirect(url_for('posts.create'))

        visibility = request.form.get('visibility', 'public')
        post = Post(
            content=content,
            author_id=current_user.id,
            visibility=visibility if visibility in POST_VISIBILITIES else 'public',
            image_data=image_data,
            image_mime=image_mime,
            link_url=link_url,
            link_title=link_title,
            link_description=link_desc,
            link_image=link_img,
        )
        db.session.add(post)
        db.session.flush()

        for tag_name in hashtags:
            tag = Hashtag.query.filter_by(name=tag_name).first()
            if not tag:
                tag = Hashtag(name=tag_name)
                db.session.add(tag)
                db.session.flush()
            post.hashtags.append(tag)

        detect_for_post(post)
        # معالجة الإشارات (@mention) في المنشور
        import re
        usernames = re.findall(r'@([\w.]+)', content)
        for username in usernames:
            mentioned_user = User.query.filter_by(username=username).first()
            if mentioned_user and mentioned_user.id != current_user.id:
                notif = Notification(
                    user_id=mentioned_user.id,
                    actor_id=current_user.id,
                    action='mention',
                    post_id=post.id
                )
                db.session.add(notif)

        db.session.commit()
        log_user_activity(current_user.id, 'post_create', {'post_id': post.id, 'attachment': 'صورة' if image_data else 'بدون مرفق'})
        flash('تم نشر المنشور بنجاح!', 'success')
        return redirect(url_for('main.index'))

    return render_template('posts/create.html', form=form)

@posts_bp.route('/comments/<int:post_id>/fragment')
@login_required
def comments_fragment(post_id):
    """Return one post's comments only when the reader opens the discussion."""
    post = Post.query.get_or_404(post_id)
    if not can_view_post(current_user, post):
        abort(403)
    return render_template('comments.html', post=post)


@posts_bp.route('/p/<public_id>')
def view_post(public_id):
    post = Post.query.filter_by(public_id=public_id).first_or_404()
    if not can_view_post(current_user, post):
        abort(403)
    return render_template('post_detail.html', post=post)
