from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app, session
from flask import abort
from flask_login import login_required, current_user, logout_user
from app.extensions import db, csrf
from app.models import User, Post, Video, Notification, Follow, Report, UserBlock
from app.forms.profile import ProfileForm
from app.utils.helpers import log_user_activity, get_user_activity_summary, get_status_icon
from app.utils.image_storage import prepare_image_data
from app.utils.profile_text import BIO_MAX_LENGTH, normalize_bio
from app.services.anter_assistant import is_anter_assistant
from app.services.privacy import can_view_profile, can_view_post, can_post_on_wall
from datetime import datetime
import re
from itsdangerous import URLSafeTimedSerializer
from app.utils.email import send_email_verification

users_bp = Blueprint('users', __name__, url_prefix='/users')
USERNAME_PATTERN = re.compile(r'[A-Za-z0-9_\u0600-\u06FF](?:[A-Za-z0-9_\u0600-\u06FF]|\.(?=[A-Za-z0-9_\u0600-\u06FF])){2,29}')
VERIFICATION_REQUEST_REASON = 'verification:account'

EMAIL_VERIFICATION_SALT = 'email-verification'
EMAIL_VERIFICATION_MAX_AGE = 24 * 60 * 60
PHONE_VERIFICATION_SALT = 'phone-verification'
PHONE_VERIFICATION_MAX_AGE = 7 * 24 * 60 * 60  # 7 أيام


def create_email_verification_token(user):
    """إنشاء توكن آمن لتأكيد البريد الإلكتروني."""
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps(
        {
            'user_id': user.id,
            'email': user.email,
        },
        salt=EMAIL_VERIFICATION_SALT,
    )


def load_email_verification_token(token):
    """فك توكن تأكيد البريد والتحقق من صلاحيته."""
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])

    try:
        data = serializer.loads(
            token,
            salt=EMAIL_VERIFICATION_SALT,
            max_age=EMAIL_VERIFICATION_MAX_AGE,
        )
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    user_id = data.get('user_id')
    token_email = data.get('email')

    if not user_id or not token_email:
        return None

    user = User.query.get(user_id)

    if not user:
        return None

    if (user.email or '').strip().lower() != str(token_email).strip().lower():
        return None

    return user



def create_phone_verification_token(user):
    """إنشاء توكن آمن لتأكيد الجوال."""
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps(
        {
            'user_id': user.id,
            'phone': user.phone,
        },
        salt=PHONE_VERIFICATION_SALT,
    )


def load_phone_verification_token(token):
    """فك توكن تأكيد الجوال والتحقق من صلاحيته."""
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])

    try:
        data = serializer.loads(
            token,
            salt=PHONE_VERIFICATION_SALT,
            max_age=PHONE_VERIFICATION_MAX_AGE,
        )
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    user_id = data.get('user_id')
    token_phone = data.get('phone')
    if not user_id or not token_phone:
        return None

    user = User.query.get(user_id)
    if not user or getattr(user, 'is_deleted', False):
        return None

    if (user.phone or '') != token_phone:
        return None

    return user


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
    ).filter(User.is_deleted.is_(False))
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
def profile(username):
    """الملف الشخصي — متاح للزوار غير المسجّلين لعرض الملفات العامة فقط."""
    user = User.query.filter_by(username=username).first_or_404()

    is_authed = bool(getattr(current_user, 'is_authenticated', False))
    viewer_is_admin = is_authed and bool(getattr(current_user, 'is_admin', False))

    # ANTER: الحسابات المحذوفة لا تُعرض لأي زائر (حتى الأدمن يراها كمرجع فقط).
    if getattr(user, 'is_deleted', False) and not viewer_is_admin:
        abort(404)

    # can_view_profile تتعامل بأمان مع الزوار المجهولين (ترفض الملفات الخاصة).
    if not can_view_profile(current_user, user):
        # للزوار غير المسجّلين: إعادة توجيه لتسجيل الدخول ثم العودة للملف.
        if not is_authed:
            return redirect(url_for('auth.login', next=request.path))
        abort(403)

    from sqlalchemy import or_, and_
    all_posts = (
        Post.query
        .filter(
            or_(
                Post.wall_owner_id == user.id,
                and_(Post.author_id == user.id, Post.wall_owner_id.is_(None)),
            )
        )
        .order_by(Post.created_at.desc())
        .all()
    )
    posts = [post for post in all_posts if can_view_post(current_user, post)]

    is_following = False
    if is_authed:
        is_following = current_user.is_following(user)

    can_write_on_wall = can_post_on_wall(current_user, user)

    return render_template(
        'profile.html',
        user=user,
        posts=posts,
        is_following=is_following,
        get_status_icon=get_status_icon,
        is_anter_assistant=is_anter_assistant(user),
        can_write_on_wall=can_write_on_wall,
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
    return render_template(
        'profile_videos.html',
        user=user,
        videos=videos,
        is_following=is_following,
        can_write_on_wall=can_post_on_wall(current_user, user),
    )

@users_bp.route('/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = ProfileForm(obj=current_user)
    if form.validate_on_submit():
        normalized_bio = normalize_bio(form.bio.data)
        changed_fields = []
        if form.name.data != current_user.name:
            changed_fields.append('الاسم')
        if normalized_bio != (current_user.bio or ''):
            changed_fields.append('السيرة الذاتية')
        current_user.name = form.name.data
        current_user.bio = normalized_bio

        # ANTER: حقول إكمال الملف (كانت في التسجيل سابقاً).
        if form.gender.data and form.gender.data != current_user.gender:
            current_user.gender = form.gender.data
            changed_fields.append('الجنس')
        if form.birth_date.data and form.birth_date.data != current_user.birth_date:
            current_user.birth_date = form.birth_date.data
            changed_fields.append('تاريخ الميلاد')
        if form.country_code.data and form.country_code.data != current_user.country_code:
            current_user.country_code = form.country_code.data
            changed_fields.append('مفتاح الدولة')
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
        # ANTER: بعد إكمال الملف الشخصي لأول مرة → الرئيسية مع كتلة الترحيب.
        if session.pop('onboarding', False):
            return redirect(url_for('main.index', welcome='1'))
        return redirect(url_for('users.profile', username=current_user.username))
    return render_template('profile_edit.html', form=form)

@users_bp.route('/settings/email/verify/send', methods=['POST'])
@login_required
def send_email_verification_request():
    """إرسال رابط تأكيد البريد الإلكتروني للمستخدم الحالي."""
    email = (current_user.email or '').strip().lower()

    if not email or email.endswith('@phone-only.anter.local'):
        flash('أضف بريدًا إلكترونيًا حقيقيًا أولاً حتى تتمكن من تأكيده.', 'warning')
        return redirect(url_for('users.settings'))

    if current_user.email_verified:
        flash('تم تأكيد بريدك الإلكتروني بالفعل.', 'info')
        return redirect(url_for('users.settings'))

    # فحص وجود طلب معلق بالفعل
    existing = Report.query.filter_by(
        reporter_id=current_user.id,
        reason='verification:email',
        status='pending',
    ).first()
    if existing:
        flash('لديك طلب تأكيد بريد قيد المراجعة. سيصلك الرابط قريبًا.', 'info')
        return redirect(url_for('users.settings'))

    # إنشاء طلب للمسؤول بدلاً من الإرسال التلقائي
    report = Report(
        reporter_id=current_user.id,
        reason='verification:email',
        details=f'طلب تأكيد البريد الإلكتروني: {email}',
    )
    db.session.add(report)
    db.session.commit()

    flash('تم إرسال طلب تأكيد البريد إلى الإدارة. سيصلك الرابط قريبًا.', 'success')
    return redirect(url_for('users.settings'))


@users_bp.route('/settings/email/verify/<token>', methods=['GET', 'POST'])
def confirm_email(token):
    """عرض صفحة تأكيد البريد وتنفيذ التأكيد بعد إرسال POST محمي بـ CSRF."""
    user = load_email_verification_token(token)

    if not user:
        flash('رابط تأكيد البريد الإلكتروني غير صالح أو انتهت صلاحيته.', 'danger')
        return redirect(url_for('auth.login'))

    if user.email_verified:
        flash('تم تأكيد بريدك الإلكتروني بالفعل.', 'info')
        if current_user.is_authenticated and current_user.id == user.id:
            return redirect(url_for('users.settings'))
        return redirect(url_for('auth.login'))

    if request.method == 'GET':
        return render_template(
            'auth/confirm_email.html',
            verification_token=token,
            verification_email=user.email,
        )

    user.email_verified = True
    db.session.commit()

    session.pop('email_verification_last_sent', None)
    log_user_activity(user.id, 'email_verification')

    if current_user.is_authenticated and current_user.id == user.id:
        flash('تم تأكيد بريدك الإلكتروني بنجاح.', 'success')
        return redirect(url_for('users.settings'))

    flash('تم تأكيد بريدك الإلكتروني بنجاح. يمكنك الآن تسجيل الدخول إلى حسابك.', 'success')
    return redirect(url_for('auth.login'))


@users_bp.route('/settings/phone/verify/<token>', methods=['GET', 'POST'])
def confirm_phone(token):
    """عرض صفحة تأكيد الجوال وتنفيذ التأكيد بعد POST محمي بـ CSRF."""
    user = load_phone_verification_token(token)

    if not user:
        flash('رابط تأكيد الجوال غير صالح أو انتهت صلاحيته.', 'danger')
        return redirect(url_for('auth.login'))

    if user.phone_verified:
        flash('تم تأكيد جوالك بالفعل.', 'info')
        if current_user.is_authenticated and current_user.id == user.id:
            return redirect(url_for('users.settings'))
        return redirect(url_for('auth.login'))

    if request.method == 'GET':
        return render_template(
            'auth/confirm_phone.html',
            verification_token=token,
            verification_phone=(user.country_code or '') + (user.phone or ''),
        )

    user.phone_verified = True
    db.session.commit()
    log_user_activity(user.id, 'phone_verification')

    # إشعار داخلي
    try:
        db.session.add(Notification(
            user_id=user.id,
            actor_id=user.id,
            action='phone_verified',
            extra_text='تم تأكيد رقم جوالك بنجاح ✅',
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()

    if current_user.is_authenticated and current_user.id == user.id:
        flash('تم تأكيد جوالك بنجاح.', 'success')
        return redirect(url_for('users.settings'))

    flash('تم تأكيد جوالك بنجاح. يمكنك الآن تسجيل الدخول.', 'success')
    return redirect(url_for('auth.login'))


@users_bp.route('/<username>/report', methods=['POST'])
@login_required
@csrf.exempt
def report_user(username):
    """بلاغ عن مستخدم — يُخزَّن في Report بنمط user-report:<reason>."""
    target = User.query.filter_by(username=username).first_or_404()

    if getattr(target, 'is_deleted', False):
        abort(404)
    if target.id == current_user.id:
        flash('لا يمكنك الإبلاغ عن نفسك.', 'warning')
        return redirect(url_for('users.profile', username=username))

    payload = request.get_json(silent=True) or {}
    is_json = request.is_json or bool(payload)
    reason = (payload.get('reason') if is_json else request.form.get('reason', '')).strip()
    details = (payload.get('details') if is_json else request.form.get('details', '')).strip()

    allowed = {
        'spam': 'محتوى مزعج أو ترويجي',
        'harassment': 'تنمر أو مضايقة',
        'hate': 'كراهية أو تحريض',
        'impersonation': 'انتحال شخصية',
        'other': 'سبب آخر',
    }

    if reason not in allowed:
        msg = 'يرجى اختيار سبب صالح للبلاغ.'
        if is_json:
            return jsonify({'success': False, 'message': msg}), 400
        flash(msg, 'danger')
        return redirect(url_for('users.profile', username=username))

    existing = Report.query.filter(
        Report.reporter_id == current_user.id,
        Report.reason == f'user-report:{reason}',
        Report.status == 'pending',
    ).filter(Report.details.like(f'%[بلاغ عن مستخدم: {username}]%')).first()

    if existing is not None:
        msg = 'لديك بلاغ معلّق بالفعل عن هذا المستخدم.'
        if is_json:
            return jsonify({'success': False, 'message': msg}), 409
        flash(msg, 'warning')
        return redirect(url_for('users.profile', username=username))

    report = Report(
        reporter_id=current_user.id,
        reason=f'user-report:{reason}',
        details=f'[بلاغ عن مستخدم: {username}]\n{details}',
        status='pending',
    )
    db.session.add(report)
    db.session.commit()

    try:
        log_user_activity(current_user.id, 'user_report', {
            'target_username': username,
            'reason': reason,
        })
    except Exception:
        pass

    msg = 'تم استلام بلاغك وسيتم مراجعته.'
    if is_json:
        return jsonify({'success': True, 'message': msg, 'report_id': report.id})
    flash(msg, 'success')
    return redirect(url_for('users.profile', username=username))


@users_bp.route('/find-friends', methods=['POST'])
@login_required
@csrf.exempt
def find_friends():
    """POST /users/find-friends
    Body: { "hashes": ["<sha256 hex>", ...] }
    يقارن البصمات بأرقام المستخدمين المعروفين ويعيد المقترحين.
    """
    import hashlib

    data = request.get_json(silent=True) or {}
    raw_hashes = data.get('hashes')

    if not isinstance(raw_hashes, list):
        return jsonify({'success': False, 'message': 'يجب إرسال قائمة hashes.'}), 400
    if len(raw_hashes) > 500:
        return jsonify({'success': False, 'message': 'عدد البصمات كبير جدًا (الحد 500).'}), 400

    hashes = set()
    for h in raw_hashes:
        if isinstance(h, str) and len(h) == 64:
            try:
                int(h, 16)
                hashes.add(h.lower())
            except ValueError:
                pass

    if not hashes:
        return jsonify({'success': True, 'suggested': [], 'matched': 0, 'submitted': 0})

    user = current_user

    # من يتابعهم المستخدم حاليًا
    already_following = {
        row.followed_id
        for row in Follow.query.filter_by(follower_id=user.id).all()
    }

    # المحظورين (في الاتجاهين)
    blocked_ids = {
        row.blocked_id
        for row in UserBlock.query.filter_by(blocker_id=user.id).all()
    }
    blocked_ids.update(
        row.blocker_id
        for row in UserBlock.query.filter_by(blocked_id=user.id).all()
    )

    # مطابقة
    from app.routes.mobile_api import _normalize_phone
    matches = []
    for other in User.query.filter(
        User.phone.isnot(None),
        User.phone != '',
        User.is_deleted.is_(False),
    ).all():
        if other.id == user.id or other.id in blocked_ids:
            continue
        normalized = _normalize_phone(other.phone)
        if not normalized:
            continue
        h = hashlib.sha256(normalized.encode('utf-8')).hexdigest()
        if h in hashes:
            matches.append({
                'id': other.id,
                'username': other.username,
                'name': other.name,
                'avatar_id': other.id,
                'isFollowing': other.id in already_following,
            })

    # ترتيب: غير المتابَعين أولًا
    matches.sort(key=lambda x: x['isFollowing'])

    return jsonify({
        'success': True,
        'suggested': matches,
        'matched': len(matches),
        'submitted': len(hashes),
    })


@users_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        section = request.form.get('_section', 'account')
        changed_fields = []

        # ---------- كلمة المرور ----------
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

        # ---------- قسم الحساب ----------
        if section == 'account':
            desired_username = request.form.get('username')
            if desired_username is not None:
                username = desired_username.strip().lstrip('@')
                if is_anter_assistant(current_user):
                    flash('اسم مستخدم مساعد أنتر محجوز ولا يمكن تغييره.', 'danger')
                    return redirect(url_for('users.settings'))
                if not USERNAME_PATTERN.fullmatch(username):
                    flash('اسم المستخدم يجب أن يتكون من 3 إلى 30 حرفاً أو رقماً، من دون مسافات.', 'danger')
                    return redirect(url_for('users.settings'))
                existing_user = User.query.filter(User.username.ilike(username)).first()
                if existing_user and existing_user.id != current_user.id:
                    flash('اسم المستخدم هذا مستخدم بالفعل.', 'danger')
                    return redirect(url_for('users.settings'))
                if username != current_user.username:
                    current_user.username = username
                    changed_fields.append('اسم المستخدم')

            gender = request.form.get('gender')
            if gender is not None:
                if gender != (current_user.gender or ''):
                    changed_fields.append('الجنس')
                current_user.gender = gender

            birth_date_str = request.form.get('birth_date')
            if birth_date_str:
                try:
                    birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
                    if birth_date != current_user.birth_date:
                        changed_fields.append('تاريخ الميلاد')
                    current_user.birth_date = birth_date
                except ValueError:
                    flash('تاريخ الميلاد غير صالح.', 'danger')
                    return redirect(url_for('users.settings'))

        # ---------- قسم الأمان ----------
        elif section == 'security':
            desired_email = request.form.get('email')
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
                    current_user.email_verified = False
                    changed_fields.append('البريد الإلكتروني')

            desired_phone = request.form.get('phone')
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

        # ---------- قسم الخصوصية ----------
        elif section == 'privacy':
            show_email = request.form.get('show_email') == 'on'
            if show_email != current_user.show_email:
                changed_fields.append('خصوصية البريد')
            current_user.show_email = show_email

            is_private = request.form.get('is_private') == 'on'
            if is_private != current_user.is_private:
                changed_fields.append('خصوصية الحساب')
            current_user.is_private = is_private

            profile_visibility = request.form.get('profile_visibility', 'public')
            if profile_visibility not in {'public', 'followers'}:
                profile_visibility = 'public'
            if is_private:
                profile_visibility = 'followers'
            if profile_visibility != current_user.profile_visibility:
                changed_fields.append('خصوصية الملف الشخصي')
            current_user.profile_visibility = profile_visibility

            wall_visibility = request.form.get('wall_visibility', 'public')
            if wall_visibility not in {'public', 'followers', 'mutual', 'none'}:
                wall_visibility = 'public'
            if wall_visibility != current_user.wall_visibility:
                changed_fields.append('خصوصية الحائط')
            current_user.wall_visibility = wall_visibility

            hide_followers = request.form.get('hide_followers') == 'on'
            if hide_followers != current_user.hide_followers:
                changed_fields.append('قوائم المتابعة')
            current_user.hide_followers = hide_followers

            show_online_status = request.form.get('show_online_status') == 'on'
            if show_online_status != current_user.show_online_status:
                changed_fields.append('حالة الظهور')
            current_user.show_online_status = show_online_status

            message_privacy = request.form.get('message_privacy')
            if message_privacy in ['everyone', 'followers', 'none']:
                current_user.message_privacy = message_privacy

            mention_privacy = request.form.get('mention_privacy')
            if mention_privacy in ['everyone', 'followers_only', 'nobody']:
                if mention_privacy != current_user.mention_privacy:
                    changed_fields.append('خصوصية الإشارات')
                current_user.mention_privacy = mention_privacy

        # ---------- حفظ ----------
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

    # بلاغات المستخدم — تبويب «المساعدة والدعم»
    # نستبعد طلبات النظام (توثيق، استعادة كلمة سر، طلبات حساب) لأنها ليست بلاغات.
    SYSTEM_REQUEST_PREFIXES = (
        'support:',
        'verification:',
        'verification-',
        'email-verification',
        'password-reset-request',
        'password-reset',
        'account-request:',
        'account_request:',
    )

    my_all = (
        Report.query
        .filter(Report.reporter_id == current_user.id)
        .order_by(Report.created_at.desc())
        .all()
    )

    def _is_system_request(r):
        reason = (r.reason or '').strip().lower()
        return any(reason.startswith(prefix) for prefix in SYSTEM_REQUEST_PREFIXES)

    from app.services.anter_user_messages import _resolve_topic

    my_content_reports = [
        r for r in my_all
        if not _is_system_request(r) and not r.reason.startswith('support:')
    ]
    my_support_requests = [
        r for r in my_all
        if r.reason.startswith('support:')
    ]

    # نضيف تسمية عربية واضحة لكل بلاغ (تُستخدم في القالب)
    for r in my_content_reports:
        r.reason_label = _resolve_topic(r.reason)
    for r in my_support_requests:
        r.reason_label = _resolve_topic(r.reason)

    # بلاغ محدد مطلوب فتحه؟ (من رابط إشعار)
    focus_report_id = request.args.get('report', type=int)

    return render_template(
        'settings.html',
        is_anter_assistant=is_anter_assistant,
        verification_request=verification_request,
        my_content_reports=my_content_reports,
        my_support_requests=my_support_requests,
        focus_report_id=focus_report_id,
    )


@users_bp.route('/settings/bio', methods=['POST'])
@login_required
def update_settings_bio():
    bio = normalize_bio(request.form.get('bio', ''))
    if len(bio) > BIO_MAX_LENGTH:
        flash(f'السيرة الذاتية يجب ألا تتجاوز {BIO_MAX_LENGTH} حرفاً.', 'danger')
        return redirect(url_for('users.settings'))

    if bio == (current_user.bio or ''):
        flash('السيرة الذاتية محفوظة بالفعل.', 'info')
        return redirect(url_for('users.settings'))

    current_user.bio = bio
    db.session.commit()
    log_user_activity(current_user.id, 'settings_update', {'fields': ['السيرة الذاتية']})
    flash('تم حفظ السيرة الذاتية بنجاح.', 'success')
    return redirect(url_for('users.settings'))


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
    if getattr(user, 'is_deleted', False):
        return jsonify({'success': False, 'message': 'الحساب غير موجود'}), 404
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
        return redirect(url_for('users.settings'))
    
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

# ============================================================
# ANTER: تعيين صورة المنشور كصورة بروفايل
# ============================================================
@users_bp.route('/set-avatar-from-post/<int:post_id>', methods=['POST'])
@login_required
@csrf.exempt
def set_avatar_from_post(post_id):
    """يسمح لصاحب المنشور بتعيين صورة منشوره كصورة ملف شخصي بضغطة واحدة."""
    from app.models import Post
    from app.utils.helpers import log_user_activity

    post = Post.query.get_or_404(post_id)

    if post.author_id != current_user.id:
        return jsonify({
            'success': False,
            'message': 'يمكنك تعيين صورة منشوراتك فقط.'
        }), 403

    if not post.image_data:
        return jsonify({
            'success': False,
            'message': 'هذا المنشور لا يحتوي على صورة قابلة للتعيين.'
        }), 400

    # نقل البيانات مباشرة (بلا معالجة جديدة، الصورة أصلًا معالَجة عند النشر).
    current_user.avatar_data = post.image_data
    current_user.avatar_mime = post.image_mime or 'image/jpeg'
    current_user.avatar = 'default.png'  # legacy path — avatar_url يفضّل DB data
    db.session.commit()

    log_user_activity(current_user.id, 'avatar_change', {'source': 'post', 'post_id': post.id})

    return jsonify({
        'success': True,
        'message': 'تم تعيين الصورة كصورة بروفايل ✓'
    })

# ============================================================
# ANTER: تغيير صورة البروفايل من صفحة المستخدم مباشرة
# ============================================================
@users_bp.route('/change-avatar', methods=['POST'])
@login_required
@csrf.exempt
def change_avatar():
    """يستقبل صورة ويُحدّث avatar_data في القاعدة فورًا."""
    from app.utils.image_storage import prepare_image_data_with_reason
    from app.utils.helpers import log_user_activity

    file = request.files.get('avatar')
    if not file or not getattr(file, 'filename', ''):
        return jsonify({'success': False, 'message': 'لم يتم اختيار صورة.'}), 400

    avatar_data, avatar_mime, reason = prepare_image_data_with_reason(file)
    if not avatar_data:
        return jsonify({
            'success': False,
            'message': reason or 'تعذر قراءة الصورة. استخدم JPG/PNG/WEBP بحجم مناسب.'
        }), 400

    current_user.avatar_data = avatar_data
    current_user.avatar_mime = avatar_mime
    current_user.avatar = 'default.png'
    db.session.commit()

    log_user_activity(current_user.id, 'avatar_change', {'source': 'profile'})

    # نبني رابطًا مُحدّثًا يحمل بصمة زمنية لتفادي الكاش
    from app.utils.media_urls import avatar_url
    import time
    fresh_url = avatar_url(current_user) + f'?v={int(time.time())}'

    return jsonify({
        'success': True,
        'message': 'تم تحديث صورة البروفايل ✓',
        'avatar_url': fresh_url,
    })


# ============================================================
# لوحة المعلومات — للموثقين فقط
# ============================================================
@users_bp.route('/creator/dashboard')
@login_required
def creator_dashboard():
    """لوحة إحصاءات احترافية لصنّاع المحتوى الموثقين."""
    from datetime import datetime, timedelta
    from sqlalchemy import func
    from app.models import Post, Video, Follow, Like, Comment, Repost, User

    if not getattr(current_user, 'is_verified', False):
        flash('هذه اللوحة للحسابات الموثقة فقط. وثّق حسابك للوصول إلى إحصاءاتك.', 'info')
        return redirect(url_for('users.profile', username=current_user.username))

    try:
        period = int(request.args.get('period', 7))
    except (ValueError, TypeError):
        period = 7
    if period not in (7, 28, 90):
        period = 7

    now = datetime.utcnow()

    def _period_stats(days, offset=0):
        end = now - timedelta(days=offset)
        start = end - timedelta(days=days)

        followers = Follow.query.filter(
            Follow.followed_id == current_user.id,
            Follow.created_at >= start,
            Follow.created_at < end,
        ).count()

        posts = Post.query.filter(
            Post.author_id == current_user.id,
            Post.created_at >= start,
            Post.created_at < end,
        ).all()
        post_ids = [p.id for p in posts]
        post_views = sum((p.views or 0) for p in posts)

        likes = comments = reposts = 0
        if post_ids:
            likes = db.session.query(func.count(Like.id)).filter(Like.post_id.in_(post_ids)).scalar() or 0
            comments = db.session.query(func.count(Comment.id)).filter(Comment.post_id.in_(post_ids)).scalar() or 0
            reposts = db.session.query(func.count(Repost.id)).filter(Repost.post_id.in_(post_ids)).scalar() or 0

        reels = Video.query.filter(
            Video.author_id == current_user.id,
            Video.created_at >= start,
            Video.created_at < end,
        ).all()
        reel_views = sum((r.views or 0) for r in reels)

        return {
            'followers': followers,
            'posts': len(posts),
            'views': post_views + reel_views,
            'likes': likes,
            'comments': comments,
            'reposts': reposts,
            'engagement': likes + comments + reposts,
        }

    current = _period_stats(period, offset=0)
    previous = _period_stats(period, offset=period)

    def _pct(curr, prev):
        if prev == 0:
            if curr == 0:
                return {'trend': 'flat', 'label': '—'}
            return {'trend': 'new', 'label': 'جديد'}
        pct = round((curr - prev) / prev * 100)
        if pct > 0:
            return {'trend': 'up', 'label': '+{}%'.format(pct)}
        if pct < 0:
            return {'trend': 'down', 'label': '{}%'.format(pct)}
        return {'trend': 'flat', 'label': '0%'}

    changes = {
        'followers': _pct(current['followers'], previous['followers']),
        'views': _pct(current['views'], previous['views']),
        'engagement': _pct(current['engagement'], previous['engagement']),
        'posts': _pct(current['posts'], previous['posts']),
    }

    followers_total = current_user.follower_count()

    all_posts = Post.query.filter_by(author_id=current_user.id).all()
    all_post_ids = [p.id for p in all_posts]
    likes_by_post = {}
    comments_by_post = {}
    reposts_by_post = {}
    if all_post_ids:
        likes_by_post = dict(db.session.query(Like.post_id, func.count(Like.id)).filter(Like.post_id.in_(all_post_ids)).group_by(Like.post_id).all())
        comments_by_post = dict(db.session.query(Comment.post_id, func.count(Comment.id)).filter(Comment.post_id.in_(all_post_ids)).group_by(Comment.post_id).all())
        reposts_by_post = dict(db.session.query(Repost.post_id, func.count(Repost.id)).filter(Repost.post_id.in_(all_post_ids)).group_by(Repost.post_id).all())

    scored_posts = []
    for p in all_posts:
        l = likes_by_post.get(p.id, 0)
        c = comments_by_post.get(p.id, 0)
        r = reposts_by_post.get(p.id, 0)
        scored_posts.append({'post': p, 'likes': l, 'comments': c, 'reposts': r, 'engagement': l + c * 3 + r * 5})
    scored_posts.sort(key=lambda x: x['engagement'], reverse=True)
    top_posts = scored_posts[:5]

    all_reels = Video.query.filter_by(author_id=current_user.id).all()
    top_reels = sorted(all_reels, key=lambda r: ((r.views or 0) * 0.1 + r.like_count() * 2 + r.comment_count() * 3), reverse=True)[:5]
    reels_count = len(all_reels)

    recent_followers = (
        db.session.query(User, Follow.created_at)
        .join(Follow, Follow.follower_id == User.id)
        .filter(Follow.followed_id == current_user.id)
        .order_by(Follow.created_at.desc())
        .limit(6).all()
    )

    return render_template(
        'creator_dashboard.html',
        period=period,
        current=current,
        previous=previous,
        changes=changes,
        followers_total=followers_total,
        top_posts=top_posts,
        top_reels=top_reels,
        reels_count=reels_count,
        recent_followers=recent_followers,
    )


