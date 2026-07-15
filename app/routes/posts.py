from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify, session, abort
from flask_login import login_required, current_user
from app import db, csrf
from app.models import Post, Comment, Like, Notification, User, Report, Repost, HiddenPost, Hashtag, post_hashtag
from app.forms.post import PostForm
from app.utils.helpers import extract_hashtags
from datetime import datetime
import os
import secrets

posts_bp = Blueprint('posts', __name__)

$(cat /tmp/create_new.py)
@posts_bp.route('/edit/<int:post_id>', methods=['GET', 'POST'])
@login_required
def edit(post_id):
    post = Post.query.get_or_404(post_id)
    if post.user_id != current_user.id and not current_user.is_admin:
        flash('ليس لديك صلاحية تعديل هذا المنشور', 'danger')
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        content = request.form.get('content', '').strip()
        if not content:
            flash('المنشور لا يمكن أن يكون فارغاً', 'danger')
            return redirect(url_for('posts.edit', post_id=post_id))
        
        post.content = content
        post.updated_at = datetime.utcnow()
        
        # تحديث الهاشتاجات
        post.hashtags.clear()
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
    
    return render_template('posts/edit.html', post=post)

@posts_bp.route('/delete/<int:post_id>', methods=['POST'])
@login_required
def delete(post_id):
    post = Post.query.get_or_404(post_id)
    if post.user_id != current_user.id and not current_user.is_admin:
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
    like = Like.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    
    if like:
        db.session.delete(like)
        liked = False
    else:
        like = Like(user_id=current_user.id, post_id=post_id)
        db.session.add(like)
        liked = True
        
        # إشعار
        if post.user_id != current_user.id:
            notification = Notification(
                user_id=post.user_id,
                type='like',
                message=f'{current_user.name} أعجب بمنشورك',
                link=f'/posts/{post_id}'
            )
            db.session.add(notification)
    
    db.session.commit()
    return jsonify({'liked': liked, 'count': post.likes.count()})

@posts_bp.route('/post/<int:post_id>')
def view(post_id):
    post = Post.query.get_or_404(post_id)
    return render_template('post_detail.html', post=post)

@posts_bp.route('/comment/<int:post_id>', methods=['POST'])
@login_required
@csrf.exempt
def comment(post_id):
    post = Post.query.get_or_404(post_id)
    content = request.form.get('content', '').strip()
    
    if not content:
        flash('التعليق لا يمكن أن يكون فارغاً', 'danger')
        return redirect(url_for('posts.view', post_id=post_id))
    
    comment = Comment(content=content, author_id=current_user.id, post_id=post_id)
    db.session.add(comment)
    db.session.commit()
    
    # إشعار
    if post.user_id != current_user.id:
        notification = Notification(
            user_id=post.user_id,
            type='comment',
            message=f'{current_user.name} علق على منشورك',
            link=f'/posts/{post_id}'
        )
        db.session.add(notification)
        db.session.commit()
    
    flash('تم إضافة التعليق بنجاح!', 'success')
    return redirect(url_for('posts.view', post_id=post_id))

@posts_bp.route('/like_comment/<int:comment_id>', methods=['POST'])
@login_required
@csrf.exempt
def like_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    like = Like.query.filter_by(user_id=current_user.id, comment_id=comment_id).first()
    
    if like:
        db.session.delete(like)
        liked = False
    else:
        like = Like(user_id=current_user.id, comment_id=comment_id)
        db.session.add(like)
        liked = True
        
        # إشعار
        if comment.user_id != current_user.id:
            notification = Notification(
                user_id=comment.user_id,
                type='like_comment',
                message=f'{current_user.name} أعجب بتعليقك',
                link=f'/posts/{comment.post_id}'
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
        if post.user_id != current_user.id:
            notification = Notification(
                user_id=post.user_id,
                type='repost',
                message=f'{current_user.name} شارك منشورك',
                link=f'/posts/{post_id}'
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
        return redirect(url_for('posts.view', post_id=post_id))
    
    # التحقق من عدم وجود بلاغ مكرر
    existing = Report.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    if existing:
        flash('لقد قمت بالفعل بتبليغ عن هذا المنشور', 'warning')
        return redirect(url_for('posts.view', post_id=post_id))
    
    report = Report(user_id=current_user.id, post_id=post_id, reason=reason)
    db.session.add(report)
    db.session.commit()
    
    flash('تم تبليغ المنشور، سيتم مراجعته من قبل الإدارة', 'success')
    return redirect(url_for('posts.view', post_id=post_id))

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

