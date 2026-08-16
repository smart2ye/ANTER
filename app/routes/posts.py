from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify, session, abort
from flask_login import login_required, current_user
from app import db, csrf
from app.models import Post, Comment, CommentLike, Like, Notification, User, Report, Repost, HiddenPost, Hashtag, post_hashtag
from app.forms.post import PostForm
from app.utils.helpers import extract_hashtags, allowed_audio_file
from app.utils.image_storage import prepare_image_data

from datetime import datetime
import os
import secrets
import uuid

posts_bp = Blueprint('posts', __name__)

@posts_bp.route('/edit/<int:post_id>', methods=['GET', 'POST'])
@login_required
def edit(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author_id != current_user.id and not current_user.is_admin:
        flash('ليس لديك صلاحية تعديل هذا المنشور', 'danger')
        return redirect(url_for('main.index'))

    form = PostForm(obj=post)
    if form.validate_on_submit():
        content = form.content.data.strip()
        if not content:
            flash('المنشور لا يمكن أن يكون فارغاً', 'danger')
            return redirect(url_for('posts.edit', post_id=post_id))
        
        post.content = content
        post.updated_at = datetime.utcnow()

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
    
    db.session.delete(post)
    db.session.commit()
    flash('تم حذف المنشور بنجاح!', 'success')
    return redirect(url_for('main.index'))

@posts_bp.route('/like/<int:post_id>', methods=['POST'])
@login_required
@csrf.exempt
def like(post_id):
    post = Post.query.get_or_404(post_id)
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
    return jsonify({
        'liked': liked,
        'reaction': reaction_type if liked else None,
        'count': post.likes.count()
    })

@posts_bp.route('/post/<int:post_id>')
def view(post_id):
    """Legacy numeric post URL; keep shared links working while moving to opaque IDs."""
    post = Post.query.get_or_404(post_id)
    return redirect(url_for('posts.view_post', public_id=post.public_id), code=301)

@posts_bp.route('/comment/<int:post_id>', methods=['POST'])
@login_required
@csrf.exempt
def comment(post_id):
    post = Post.query.get_or_404(post_id)
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
    
    flash('تم إضافة التعليق بنجاح!', 'success')
    return redirect(url_for('posts.view_post', public_id=post.public_id))

@posts_bp.route('/like_comment/<int:comment_id>', methods=['POST'])
@login_required
@csrf.exempt
def like_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
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
    return jsonify({'liked': liked, 'count': comment.likes.count()})

@posts_bp.route('/repost/<int:post_id>', methods=['POST'])
@login_required
@csrf.exempt
def repost(post_id):
    post = Post.query.get_or_404(post_id)
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
    return jsonify({'reposted': reposted, 'count': post.reposts.count()})

@posts_bp.route('/report/<int:post_id>', methods=['POST'])
@login_required
@csrf.exempt
def report(post_id):
    post = Post.query.get_or_404(post_id)
    reason = request.form.get('reason', '').strip()
    
    if not reason:
        flash('يرجى كتابة سبب التبليغ', 'danger')
        return redirect(url_for('posts.view_post', public_id=post.public_id))
    
    # التحقق من عدم وجود بلاغ مكرر
    existing = Report.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    if existing:
        flash('لقد قمت بالفعل بتبليغ عن هذا المنشور', 'warning')
        return redirect(url_for('posts.view_post', public_id=post.public_id))
    
    report = Report(user_id=current_user.id, post_id=post_id, reason=reason)
    db.session.add(report)
    db.session.commit()
    
    flash('تم تبليغ المنشور، سيتم مراجعته من قبل الإدارة', 'success')
    return redirect(url_for('posts.view_post', public_id=post.public_id))

@posts_bp.route('/hide/<int:post_id>', methods=['POST'])
@login_required
@csrf.exempt
def hide(post_id):
    post = Post.query.get_or_404(post_id)
    
    hidden = HiddenPost.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    if not hidden:
        hidden = HiddenPost(user_id=current_user.id, post_id=post_id)
        db.session.add(hidden)
        db.session.commit()
    
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

        # تخزين الصورة داخل قاعدة البيانات الدائمة عند إرفاقها بالمنشور.
        uploaded_image = form.image.data
        image_data, image_mime = (None, None)
        if uploaded_image and getattr(uploaded_image, 'filename', ''):
            image_data, image_mime = prepare_image_data(uploaded_image)
            if not image_data:
                flash('تعذر قراءة الصورة. استخدم JPG أو PNG أو GIF أو WEBP بحجم ضمن الحد المسموح.', 'danger')
                return redirect(url_for('posts.create'))

        post = Post(
            content=content,
            author_id=current_user.id,
            image_data=image_data,
            image_mime=image_mime,
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
        flash('تم نشر المنشور بنجاح!', 'success')
        return redirect(url_for('main.index'))

    return render_template('posts/create.html', form=form)

@posts_bp.route('/comments/<int:post_id>/fragment')
@login_required
def comments_fragment(post_id):
    """Return one post's comments only when the reader opens the discussion."""
    post = Post.query.get_or_404(post_id)
    return render_template('comments.html', post=post)


@posts_bp.route('/p/<public_id>')
def view_post(public_id):
    post = Post.query.filter_by(public_id=public_id).first_or_404()
    return render_template('post_detail.html', post=post)
