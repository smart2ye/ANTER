from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.extensions import db, csrf
from app.models import Post, Comment, Like, CommentLike, Notification, Report
from app.forms.post import PostForm
from app.utils.helpers import save_uploaded_image, parse_mentions, process_hashtags
from datetime import datetime

posts_bp = Blueprint('posts', __name__, url_prefix='/posts')

@posts_bp.route('/create', methods=['GET', 'POST'])
@login_required
@csrf.exempt
def create():
    if request.method == 'POST':
        content = request.form.get('content', '').strip()
        if not content:
            flash('المحتوى مطلوب.', 'danger')
            return redirect(url_for('posts.create'))
        
        image = ''
        if 'image' in request.files and request.files['image'].filename:
            image = save_uploaded_image(request.files['image'], 'posts')
        
        post = Post(content=content, image=image, author_id=current_user.id)
        db.session.add(post)
        db.session.commit()
        
        # معالجة الوسوم
        process_hashtags(post.id, content)
        
        # إذا كان طلب AJAX
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'post_id': post.id})
        
        flash('تم نشر المنشور بنجاح.', 'success')
        return redirect(url_for('main.index'))
    
    form = PostForm()
    return render_template('posts/create.html', form=form)

# ============================================
# باقي المسارات (like, comment, react, etc.)
# ============================================
@posts_bp.route('/edit/<int:post_id>', methods=['GET', 'POST'])
@login_required
def edit(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author_id != current_user.id:
        flash('لا يمكنك تعديل هذا المنشور.', 'danger')
        return redirect(url_for('main.index'))
    form = PostForm(obj=post)
    if form.validate_on_submit():
        post.content = form.content.data
        if form.image.data:
            post.image = save_uploaded_image(form.image.data, 'posts')
        post.updated_at = datetime.utcnow()
        db.session.commit()
        flash('تم تحديث المنشور.', 'success')
        return redirect(url_for('main.index'))
    return render_template('posts/edit.html', form=form, post=post)

@posts_bp.route('/delete/<int:post_id>', methods=['POST'])
@login_required
@csrf.exempt
def delete(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author_id != current_user.id:
        return jsonify({'success': False, 'message': 'غير مسموح'}), 403
    db.session.delete(post)
    db.session.commit()
    return jsonify({'success': True})

@posts_bp.route('/react/<int:post_id>', methods=['POST'])
@login_required
@csrf.exempt
def react(post_id):
    from sqlalchemy import func
    post = Post.query.get_or_404(post_id)
    reaction_type = request.json.get('reaction', 'like')
    valid_reactions = ['like', 'love', 'haha', 'angry', 'sad']
    if reaction_type not in valid_reactions:
        return jsonify({'success': False, 'message': 'نوع تفاعل غير صالح'}), 400
    
    existing_like = Like.query.filter_by(post_id=post_id, user_id=current_user.id).first()
    if existing_like:
        if existing_like.reaction_type == reaction_type:
            db.session.delete(existing_like)
            db.session.commit()
            return jsonify({
                'success': True, 'action': 'removed', 'reaction': reaction_type,
                'counts': get_reaction_counts(post_id)
            })
        else:
            existing_like.reaction_type = reaction_type
            db.session.commit()
            return jsonify({
                'success': True, 'action': 'updated', 'reaction': reaction_type,
                'counts': get_reaction_counts(post_id)
            })
    else:
        like = Like(post_id=post_id, user_id=current_user.id, reaction_type=reaction_type)
        db.session.add(like)
        if post.author_id != current_user.id:
            notif = Notification(user_id=post.author_id, actor_id=current_user.id, action=f'react_{reaction_type}', post_id=post.id)
            db.session.add(notif)
        db.session.commit()
        return jsonify({
            'success': True, 'action': 'added', 'reaction': reaction_type,
            'counts': get_reaction_counts(post_id)
        })

@posts_bp.route('/comment/<int:post_id>', methods=['POST'])
@login_required
@csrf.exempt
def comment(post_id):
    post = Post.query.get_or_404(post_id)
    content = request.form.get('content', '').strip()
    parent_id = request.form.get('parent_id', type=int)
    if content:
        comment = Comment(content=content, author_id=current_user.id, post_id=post.id)
        if parent_id:
            comment.parent_id = parent_id
            parent_comment = Comment.query.get(parent_id)
            if parent_comment and parent_comment.author_id != current_user.id:
                notif = Notification(user_id=parent_comment.author_id, actor_id=current_user.id, action='reply', post_id=post.id)
                db.session.add(notif)
        else:
            if post.author_id != current_user.id:
                notif = Notification(user_id=post.author_id, actor_id=current_user.id, action='comment', post_id=post.id)
                db.session.add(notif)
        db.session.add(comment)
        db.session.commit()
        flash('تم إضافة التعليق.', 'success')
    else:
        flash('التعليق لا يمكن أن يكون فارغاً.', 'danger')
    return redirect(url_for('posts.view_post', post_id=post.id))

@posts_bp.route('/like_comment/<int:comment_id>', methods=['POST'])
@login_required
@csrf.exempt
def like_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    like = CommentLike.query.filter_by(comment_id=comment_id, user_id=current_user.id).first()
    if like:
        db.session.delete(like)
        liked = False
    else:
        like = CommentLike(comment_id=comment_id, user_id=current_user.id)
        db.session.add(like)
        liked = True
    db.session.commit()
    return jsonify({'liked': liked, 'count': comment.like_count()})

@posts_bp.route('/post/<int:post_id>')
@login_required
def view_post(post_id):
    post = Post.query.get_or_404(post_id)
    comments = post.comments.filter_by(parent_id=None).order_by(Comment.created_at.asc()).all()
    return render_template('post_detail.html', post=post, comments=comments)

@posts_bp.route('/report', methods=['POST'])
@login_required
@csrf.exempt
def report():
    data = request.get_json()
    post_id = data.get('post_id')
    reason = data.get('reason')
    details = data.get('details', '')
    if not post_id or not reason:
        return jsonify({'success': False, 'message': 'بيانات ناقصة'}), 400
    post = Post.query.get(post_id)
    if not post:
        return jsonify({'success': False, 'message': 'المنشور غير موجود'}), 404
    if post.author_id == current_user.id:
        return jsonify({'success': False, 'message': 'لا يمكن الإبلاغ عن منشورك الخاص'}), 400
    existing = Report.query.filter_by(reporter_id=current_user.id, post_id=post_id, status='pending').first()
    if existing:
        return jsonify({'success': False, 'message': 'سبق لك الإبلاغ عن هذا المنشور'}), 400
    report = Report(
        reporter_id=current_user.id,
        post_id=post_id,
        reason=reason,
        details=details
    )
    db.session.add(report)
    db.session.commit()
    return jsonify({'success': True, 'message': 'تم إرسال البلاغ بنجاح'})

@posts_bp.route('/hide/<int:post_id>', methods=['POST'])
@login_required
@csrf.exempt
def hide(post_id):
    from app.models import HiddenPost
    post = Post.query.get_or_404(post_id)
    if post.author_id == current_user.id:
        return jsonify({'success': False, 'message': 'لا يمكن إخفاء منشورك الخاص'}), 400
    existing = HiddenPost.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    if existing:
        return jsonify({'success': False, 'message': 'المنشور مخفي بالفعل'}), 400
    hidden = HiddenPost(user_id=current_user.id, post_id=post_id)
    db.session.add(hidden)
    db.session.commit()
    return jsonify({'success': True, 'message': 'تم إخفاء المنشور'})

def get_reaction_counts(post_id):
    from sqlalchemy import func
    counts = db.session.query(
        Like.reaction_type,
        func.count(Like.id).label('count')
    ).filter(Like.post_id == post_id).group_by(Like.reaction_type).all()
    result = {'like': 0, 'love': 0, 'haha': 0, 'angry': 0, 'sad': 0}
    for c in counts:
        result[c.reaction_type] = c.count
    return result
