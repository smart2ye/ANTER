from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app, session
from flask import abort
from flask_login import login_required, current_user, logout_user
from app.extensions import db, csrf
from app.models import User, Post, Video, Notification, Follow, Report
from app.forms.profile import ProfileForm
from app.utils.helpers import log_user_activity, get_user_activity_summary, get_status_icon
from app.utils.image_storage import prepare_image_data
from app.services.anter_assistant import is_anter_assistant
from app.services.privacy import can_view_profile, can_view_post
from datetime import datetime
import re

users_bp = Blueprint('users', __name__, url_prefix='/users')
USERNAME_PATTERN = re.compile(r'[A-Za-z0-9_\u0600-\u06FF](?:[A-Za-z0-9_\u0600-\u06FF]|\.(?=[A-Za-z0-9_\u0600-\u06FF])){2,29}')
VERIFICATION_REQUEST_REASON = 'verification:account'

@users_bp.route('/api/search', methods=['GET'])
@login_required
def api_search():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])
    
    # إزالة علامة @ إن وجدت في بداية البحث
    if query.startswith('@'):
        query = query[1:]
        
    users_query = User.query.filter(
        (User.username.ilike(f'%{query}%')) | (User.name.ilike(f'%{query}%'))
    )
    if request.args.get('following_only') == '1':
        # تستخدم إعادة توجيه الرسائل هذا الخيار حتى لا تعرض إلا الحسابات التي يتابعها المستخدم الحالي.
        users_query = users_query.join(Follow, Follow.followed_id == User.id).filter(
            Follow.follower_id == current_user.id,
        )
    users = users_query.limit(8).all()
    
    from app.utils.media_urls import avatar_url
    result = [{
        'id': u.id,
        'username': u.username,
        'name': u.name or u.username,
        'avatar': avatar_url(u),
        'is_verified': u.is_verified
    } for u in users]
    
    return jsonify(result)

@users_bp.route('/<username>')
@login_required
def profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    if not can_view_profile(current_user, user):
        abort(403)
    posts = [post for post in user.posts.order_by(Post.created_at.desc()).all() if can_view_post(current_user, post)]
    is_following = current_user.is_following(user)
    return render_template(
        'profile.html',
        user=user,
        posts=posts,
        is_following=is_following,
        get_status_icon=get_status_icon,
        is_anter_assistant=is_anter_assistant(user),
    )

@users_bp.route('/<username>/followers')
@login_required
def followers(username):
    user = User.query.filter_by(username=username).first_or_404()
    if not can_view_profile(current_user, user) or (user.hide_followers and current_user.id != user.id and not current_user.is_admin):
        abort(403)
    followers = user.followers.order_by(Follow.created_at.desc()).all()
    follower_users = [f.follower for f in followers]
    return render_template('followers.html', user=user, users=follower_users, type='followers')

@users_bp.route('/<username>/following')
@login_required
def following(username):
    user = User.query.filter_by(username=username).first_or_404()
    if not can_view_profile(current_user, user) or (user.hide_followers and current_user.id != user.id and not current_user.is_admin):
        abort(403)
    following_users = [f.followed for f in user.following.order_by(Follow.created_at.desc()).all()]
    return render_template('followers.html', user=user, users=following_users, type='following')

@users_bp.route('/<username>/videos')
@login_required
def user_videos(username):
    user = User.query.filter_by(username=username).first_or_404()
    if not can_view_profile(current_user, user):
        abort(403)
    videos = user.videos.order_by(Video.created_at.desc()).all()
    is_following = current_user.is_following(user)
    return render_template('profile_videos.html', user=user, videos=videos, is_following=is_following)

@users_bp.route('/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = ProfileForm(obj=current_user)
    if form.validate_on_submit():
        changed_fields = []
        if form.name.data != current_user.name:
            changed_fields.append('الاسم')
        if form.bio.data != current_user.bio:
            changed_fields.append('النبذة')
        current_user.name = form.name.data
        current_user.bio = form.bio.data
        if form.avatar.data:
            avatar_data, avatar_mime = prepare_image_data(form.avatar.data)
            if avatar_data:
                current_user.avatar_data = avatar_data
                current_user.avatar_mime = avatar_mime
                # Keep the legacy path for old clients; avatar_url prefers the DB data.
                current_user.avatar = 'default.png'
                changed_fields.append('صورة الملف الشخصي')
            else:
                flash('تعذر قراءة صورة البروفايل أو أنها أكبر من الحد المسموح.', 'danger')
        db.session.commit()
        if changed_fields:
            log_user_activity(current_user.id, 'profile_update', {'fields': changed_fields})
            if 'صورة الملف الشخصي' in changed_fields:
                log_user_activity(current_user.id, 'avatar_change')
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
            log_user_activity(current_user.id, 'password_change')
            flash('تم تغيير كلمة المرور بنجاح.', 'success')
            return redirect(url_for('users.settings'))
        
        # تحديث المعلومات الشخصية
        desired_username = request.form.get('username')
        desired_email = request.form.get('email')
        desired_phone = request.form.get('phone')
        gender = request.form.get('gender')
        birth_date_str = request.form.get('birth_date')
        bio = request.form.get('bio')
        show_email = request.form.get('show_email') == 'on'
        is_private = request.form.get('is_private') == 'on'
        profile_visibility = request.form.get('profile_visibility', 'public')
        hide_followers = request.form.get('hide_followers') == 'on'
        show_online_status = request.form.get('show_online_status') == 'on'
        message_privacy = request.form.get('message_privacy')
        
        changed_fields = []
        if desired_username is not None:
            username = desired_username.strip().lstrip('@')
            if is_anter_assistant(current_user):
                flash('اسم مستخدم مساعد أنتر محجوز ولا يمكن تغييره.', 'danger')
                return redirect(url_for('users.settings'))
            if not USERNAME_PATTERN.fullmatch(username):
                flash('اسم المستخدم يجب أن يتكون من 3 إلى 30 حرفاً أو رقماً، من دون مسافات. يمكن استخدام الشرطة السفلية _ والنقطة بين أجزاء الاسم فقط.', 'danger')
                return redirect(url_for('users.settings'))
            existing_user = User.query.filter(User.username.ilike(username)).first()
            if existing_user and existing_user.id != current_user.id:
                flash('اسم المستخدم هذا مستخدم بالفعل. جرّب اسماً آخر.', 'danger')
                return redirect(url_for('users.settings'))
            if username != current_user.username:
                current_user.username = username
                changed_fields.append('اسم المستخدم')

        if desired_email is not None:
            email = desired_email.strip().lower()
            if email and email != current_user.email:
                if not current_user.check_password(request.form.get('contact_password', '')):
                    flash('أدخل كلمة المرور الحالية لتغيير البريد الإلكتروني أو رقم الجوال.', 'danger')
                    return redirect(url_for('users.settings'))
                existing_email = User.query.filter(User.email.ilike(email)).first()
                if existing_email and existing_email.id != current_user.id:
                    flash('هذا البريد الإلكتروني مستخدم بالفعل.', 'danger')
                    return redirect(url_for('users.settings'))
                current_user.email = email
                changed_fields.append('البريد الإلكتروني')

        if desired_phone is not None:
            phone = desired_phone.strip().replace(' ', '')
            if phone != (current_user.phone or ''):
                if not current_user.check_password(request.form.get('contact_password', '')):
                    flash('أدخل كلمة المرور الحالية لتغيير البريد الإلكتروني أو رقم الجوال.', 'danger')
                    return redirect(url_for('users.settings'))
                existing_phone = User.query.filter_by(phone=phone or None).first() if phone else None
                if existing_phone and existing_phone.id != current_user.id:
                    flash('رقم الجوال مستخدم بالفعل.', 'danger')
                    return redirect(url_for('users.settings'))
                current_user.phone = phone or None
                current_user.phone_verified = False
                changed_fields.append('رقم الجوال')

        if gender is not None:
            if gender != (current_user.gender or ''):
                changed_fields.append('الجنس')
            current_user.gender = gender
        if birth_date_str:
            try:
                birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
                if birth_date != current_user.birth_date:
                    changed_fields.append('تاريخ الميلاد')
                current_user.birth_date = birth_date
            except ValueError:
                flash('تاريخ الميلاد غير صالح.', 'danger')
                return redirect(url_for('users.settings'))
        if bio is not None:
            if bio[:200] != (current_user.bio or ''):
                changed_fields.append('النبذة')
            current_user.bio = bio[:200]
        if show_email != current_user.show_email:
            changed_fields.append('خصوصية البريد')
        if is_private != current_user.is_private:
            changed_fields.append('خصوصية الحساب')
        if profile_visibility not in {'public', 'followers'}:
            profile_visibility = 'public'
        if is_private:
            profile_visibility = 'followers'
        if profile_visibility != current_user.profile_visibility:
            changed_fields.append('خصوصية الملف الشخصي')
        if hide_followers != current_user.hide_followers:
            changed_fields.append('قوائم المتابعة')
        if show_online_status != current_user.show_online_status:
            changed_fields.append('حالة الظهور')
        current_user.show_email = show_email
        current_user.is_private = is_private
        current_user.profile_visibility = profile_visibility
        current_user.hide_followers = hide_followers
        current_user.show_online_status = show_online_status
        if message_privacy in ['everyone', 'followers', 'none']:
            current_user.message_privacy = message_privacy
        
        db.session.commit()
        if changed_fields:
            log_user_activity(current_user.id, 'settings_update', {'fields': changed_fields})
            if 'اسم المستخدم' in changed_fields:
                log_user_activity(current_user.id, 'username_change')
            if 'البريد الإلكتروني' in changed_fields:
                log_user_activity(current_user.id, 'email_change')
            if 'رقم الجوال' in changed_fields:
                log_user_activity(current_user.id, 'phone_change')
        flash('تم تحديث الإعدادات بنجاح.', 'success')
        return redirect(url_for('users.settings'))
    
    verification_request = Report.query.filter_by(
        reporter_id=current_user.id,
        reason=VERIFICATION_REQUEST_REASON,
    ).order_by(Report.created_at.desc()).first()
    return render_template(
        'settings.html',
        is_anter_assistant=is_anter_assistant,
        verification_request=verification_request,
    )


@users_bp.route('/verification-request', methods=['POST'])
@login_required
def request_verification():
    if current_user.is_verified:
        flash('حسابك موثق بالفعل.', 'info')
        return redirect(url_for('users.settings'))

    details = request.form.get('details', '').strip()
    if len(details) < 20 or len(details) > 500:
        flash('اكتب سبب طلب التوثيق في 20 إلى 500 حرف.', 'danger')
        return redirect(url_for('users.settings'))

    pending_request = Report.query.filter_by(
        reporter_id=current_user.id,
        reason=VERIFICATION_REQUEST_REASON,
        status='pending',
    ).first()
    if pending_request:
        flash('لديك طلب توثيق قيد المراجعة بالفعل.', 'info')
        return redirect(url_for('users.settings'))

    db.session.add(Report(
        reporter_id=current_user.id,
        reason=VERIFICATION_REQUEST_REASON,
        details=details,
        status='pending',
    ))
    db.session.commit()
    log_user_activity(current_user.id, 'verification_request')
    flash('تم إرسال طلب التوثيق للإدارة لمراجعته.', 'success')
    return redirect(url_for('users.settings'))

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
    log_user_activity(current_user.id, 'follow', {'target_username': user.username})
    return jsonify({'success': True, 'following': True})

@users_bp.route('/unfollow/<int:user_id>', methods=['POST'])
@login_required
@csrf.exempt
def unfollow(user_id):
    user = User.query.get_or_404(user_id)
    current_user.unfollow(user)
    db.session.commit()
    log_user_activity(current_user.id, 'unfollow', {'target_username': user.username})
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

# ============================================
# سجل النشاط وتنزيل البيانات
# ============================================
@users_bp.route('/activity')
@login_required
def activity_log():
    activities = get_user_activity_summary(current_user.id, 100)
    return render_template('activity_log.html', activities=activities)

@users_bp.route('/download_data')
@login_required
def download_data():
    import json
    from datetime import datetime
    from app.models import UserActivity
    
    user_data = {
        'user': {
            'id': current_user.id,
            'username': current_user.username,
            'email': current_user.email,
            'name': current_user.name,
            'bio': current_user.bio,
            'avatar': current_user.avatar,
            'created_at': current_user.created_at.isoformat() if current_user.created_at else None,
            'is_verified': current_user.is_verified,
        },
        'posts': [{'id': p.id, 'content': p.content, 'image': p.image, 'created_at': p.created_at.isoformat()} for p in current_user.posts.all()],
        'comments': [{'id': c.id, 'content': c.content, 'post_id': c.post_id, 'created_at': c.created_at.isoformat()} for c in current_user.comments.all()],
        'messages_sent': [{'id': m.id, 'receiver_id': m.receiver_id, 'content': m.content, 'created_at': m.created_at.isoformat()} for m in current_user.messages_sent.all()],
        'messages_received': [{'id': m.id, 'sender_id': m.sender_id, 'content': m.content, 'created_at': m.created_at.isoformat()} for m in current_user.messages_received.all()],
        'followers': [{'follower_id': f.follower_id, 'created_at': f.created_at.isoformat()} for f in current_user.followers.all()],
        'following': [{'followed_id': f.followed_id, 'created_at': f.created_at.isoformat()} for f in current_user.following.all()],
        'likes': [{'post_id': l.post_id, 'reaction_type': l.reaction_type, 'created_at': l.created_at.isoformat()} for l in current_user.likes.all()],
        'activities': [{'action': a.action, 'ip': a.ip_address, 'browser': a.browser, 'os': a.os, 'device': a.device_type, 'created_at': a.created_at.isoformat()} for a in current_user.activities.order_by(UserActivity.created_at.desc()).limit(200).all()]
    }
    
    log_user_activity(current_user.id, 'download_data')
    
    filename = f"ANTER_data_{current_user.username}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    response = jsonify(user_data)
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'
    return response
