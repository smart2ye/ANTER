from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user, logout_user
from app.extensions import db, csrf
from app.models import User, Post, Video, Notification, Follow
from app.forms.profile import ProfileForm
from app.utils.helpers import save_uploaded_image
import os
from datetime import datetime

users_bp = Blueprint('users', __name__, url_prefix='/users')

@users_bp.route('/<username>')
@login_required
def profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    posts = user.posts.order_by(Post.created_at.desc()).all()
    is_following = current_user.is_following(user)
    return render_template('profile.html', user=user, posts=posts, is_following=is_following)

@users_bp.route('/<username>/followers')
@login_required
def followers(username):
    user = User.query.filter_by(username=username).first_or_404()
    followers = user.followers.order_by(Follow.created_at.desc()).all()
    follower_users = [f.follower for f in followers]
    return render_template('followers.html', user=user, users=follower_users, type='followers')

@users_bp.route('/<username>/following')
@login_required
def following(username):
    user = User.query.filter_by(username=username).first_or_404()
    following_users = [f.followed for f in user.following.order_by(Follow.created_at.desc()).all()]
    return render_template('followers.html', user=user, users=following_users, type='following')

@users_bp.route('/<username>/videos')
@login_required
def user_videos(username):
    user = User.query.filter_by(username=username).first_or_404()
    videos = user.videos.order_by(Video.created_at.desc()).all()
    is_following = current_user.is_following(user)
    return render_template('profile_videos.html', user=user, videos=videos, is_following=is_following)

@users_bp.route('/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = ProfileForm(obj=current_user)
    if form.validate_on_submit():
        current_user.name = form.name.data
        current_user.bio = form.bio.data
        if form.avatar.data:
            old_avatar = current_user.avatar
            avatar_path = save_uploaded_image(form.avatar.data, 'avatars')
            if avatar_path:
                current_user.avatar = avatar_path
                if old_avatar and old_avatar != 'default.png':
                    old_path = os.path.join(current_app.config['UPLOAD_FOLDER'], old_avatar)
                    if os.path.exists(old_path):
                        os.remove(old_path)
        db.session.commit()
        flash('تم تحديث الملف الشخصي بنجاح.', 'success')
        return redirect(url_for('users.profile', username=current_user.username))
    return render_template('profile_edit.html', form=form)

@users_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@csrf.exempt
def settings():
    if request.method == 'POST':
        # تغيير كلمة المرور
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if any([current_password, new_password, confirm_password]):
            if not all([current_password, new_password, confirm_password]):
                flash('جميع حقول كلمة المرور مطلوبة.', 'danger')
                return redirect(url_for('users.settings'))
            if not current_user.check_password(current_password):
                flash('كلمة المرور الحالية غير صحيحة.', 'danger')
                return redirect(url_for('users.settings'))
            if new_password != confirm_password:
                flash('كلمة المرور الجديدة غير متطابقة.', 'danger')
                return redirect(url_for('users.settings'))
            if len(new_password) < 6:
                flash('كلمة المرور يجب أن تكون 6 أحرف على الأقل.', 'danger')
                return redirect(url_for('users.settings'))
            current_user.set_password(new_password)
            db.session.commit()
            flash('تم تغيير كلمة المرور بنجاح.', 'success')
            return redirect(url_for('users.settings'))
        
        # تحديث المعلومات الشخصية
        gender = request.form.get('gender')
        birth_date_str = request.form.get('birth_date')
        bio = request.form.get('bio')
        show_email = request.form.get('show_email') == 'on'
        is_private = request.form.get('is_private') == 'on'
        message_privacy = request.form.get('message_privacy')
        
        if gender is not None:
            current_user.gender = gender
        if birth_date_str:
            try:
                current_user.birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
            except ValueError:
                flash('تاريخ الميلاد غير صالح.', 'danger')
                return redirect(url_for('users.settings'))
        if bio is not None:
            current_user.bio = bio[:200]
        current_user.show_email = show_email
        current_user.is_private = is_private
        if message_privacy in ['everyone', 'followers', 'none']:
            current_user.message_privacy = message_privacy
        
        db.session.commit()
        flash('تم تحديث الإعدادات بنجاح.', 'success')
        return redirect(url_for('users.settings'))
    
    return render_template('settings.html')

@users_bp.route('/follow/<int:user_id>', methods=['POST'])
@login_required
@csrf.exempt
def follow(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        return jsonify({'success': False, 'message': 'لا يمكن متابعة نفسك'}), 400
    current_user.follow(user)
    notif = Notification(user_id=user.id, actor_id=current_user.id, action='follow')
    db.session.add(notif)
    db.session.commit()
    return jsonify({'success': True, 'following': True})

@users_bp.route('/unfollow/<int:user_id>', methods=['POST'])
@login_required
@csrf.exempt
def unfollow(user_id):
    user = User.query.get_or_404(user_id)
    current_user.unfollow(user)
    db.session.commit()
    return jsonify({'success': True, 'following': False})

@users_bp.route('/delete_account', methods=['POST'])
@login_required
def delete_account():
    password = request.form.get('password', '').strip()
    if not current_user.check_password(password):
        flash('كلمة المرور غير صحيحة.', 'danger')
        return redirect(url_for('users.profile', username=current_user.username))
    
    from app.models import Post, Comment, Message, Follow, Like, Notification, CommentLike
    
    Post.query.filter_by(author_id=current_user.id).delete()
    Comment.query.filter_by(author_id=current_user.id).delete()
    Message.query.filter((Message.sender_id == current_user.id) | (Message.receiver_id == current_user.id)).delete()
    Follow.query.filter((Follow.follower_id == current_user.id) | (Follow.followed_id == current_user.id)).delete()
    Like.query.filter_by(user_id=current_user.id).delete()
    CommentLike.query.filter_by(user_id=current_user.id).delete()
    Notification.query.filter((Notification.user_id == current_user.id) | (Notification.actor_id == current_user.id)).delete()
    
    db.session.delete(current_user)
    db.session.commit()
    logout_user()
    flash('تم حذف حسابك بنجاح.', 'success')
    return redirect(url_for('auth.login'))
