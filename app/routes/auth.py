from flask import Blueprint, abort, render_template, redirect, url_for, flash, request, current_app, session
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db
from app.models import User
from app.forms.auth import LoginForm, RegistrationForm, ResetPasswordRequestForm, ResetPasswordForm
from itsdangerous import URLSafeTimedSerializer
from app.utils.helpers import log_user_activity
from app.services.anter_assistant import ensure_anter_assistant_user, follow_anter_assistant_for_user
from app.services.anter_user_messages import send_welcome_message
from app.services.anter_account_switching import (
    can_switch_back,
    can_switch_to_assistant,
    get_managed_assistant,
)
from app.utils.public_ids import generate_public_id

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = LoginForm()
    if form.validate_on_submit():
        # البحث باستخدام اسم المستخدم أو البريد أو رقم الهاتف
        user = User.query.filter(
            (User.username == form.username.data) |
            (User.email == form.username.data) |
            (User.phone == form.username.data)
        ).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=True)
            log_user_activity(user.id, "login")
            next_page = request.args.get('next')
            flash('✅ تم تسجيل الدخول بنجاح!', 'success')
            return redirect(next_page or url_for('main.index'))
        else:
            flash('❌ اسم المستخدم أو كلمة المرور غير صحيحة.', 'danger')
    return render_template('auth/login.html', form=form)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        # المعرف العام يُنشأ تلقائياً ليكون رابطاً عشوائياً لا يحتاج المستخدم إلى اختياره أو تذكره.
        username = generate_public_id('u')
        while User.query.filter_by(username=username).first() is not None:
            username = generate_public_id('u')

        email = (form.email.data or '').strip().lower()
        # قاعدة البيانات القديمة تتطلب بريداً غير فارغ. لحساب الجوال فقط ننشئ قيمة داخلية
        # مرتبطة بالمعرف العشوائي ولا تُعرض في الملف الشخصي ولا تصلح كعنوان بريد حقيقي.
        if not email:
            email = f'{username}@phone-only.anter.local'

        phone = (form.phone.data or '').strip()
        default_avatar = (
            'img/default_avatar_female.png'
            if form.gender.data == 'female'
            else 'img/default_avatar_male.png'
        )
        user = User(
            username=username,
            email=email,
            name=form.name.data.strip(),
            avatar=default_avatar,
            gender=form.gender.data or '',
            birth_date=form.birth_date.data,
            country_code=form.country_code.data,
            phone=form.country_code.data + phone if phone else None,
            phone_verified=False,
            terms_agreed=form.terms_agreed.data
        )
        user.set_password(form.password.data)
        assistant = ensure_anter_assistant_user()
        db.session.add(user)
        db.session.flush()
        follow_anter_assistant_for_user(user, assistant)
        send_welcome_message(user)
        db.session.commit()
        flash('✅ تم التسجيل بنجاح، يمكنك الدخول الآن.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/register.html', form=form)

@auth_bp.route('/switch-to-assistant', methods=['POST'])
@login_required
def switch_to_assistant():
    """Allow only the configured founder account to manage the assistant session."""
    if not can_switch_to_assistant(current_user):
        abort(403)

    assistant = get_managed_assistant()
    session['anter_assistant_switch_owner_id'] = current_user.id
    login_user(assistant, remember=False, force=True)
    session.modified = True
    flash('تم التبديل إلى حساب مساعد أنتر. يمكنك العودة إلى حسابك من القائمة.', 'success')
    return redirect(request.referrer or url_for('main.index'))


@auth_bp.route('/switch-back-to-owner', methods=['POST'])
@login_required
def switch_back_to_owner():
    owner_id = session.get('anter_assistant_switch_owner_id')
    if not can_switch_back(current_user, owner_id):
        abort(403)

    owner = User.query.get_or_404(owner_id)
    session.pop('anter_assistant_switch_owner_id', None)
    login_user(owner, remember=False, force=True)
    session.modified = True
    flash('تمت العودة إلى حسابك الشخصي.', 'success')
    return redirect(url_for('main.index'))


@auth_bp.route('/logout')
@login_required
def logout():
    log_user_activity(current_user.id, "logout")
    session.pop('anter_assistant_switch_owner_id', None)
    logout_user()
    flash('✅ تم تسجيل الخروج بنجاح، نراكم قريباً!', 'success')
    return redirect(url_for('auth.login'))

@auth_bp.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = ResetPasswordRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
            token = s.dumps(user.id, salt='password-reset')
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            # تم إخفاء الرابط تماماً من الشاشة لمنع استغلاله من قبل أي شخص يعرف البريد
            # في الإنتاج يتم إرسال هذا الرابط حصرياً عبر البريد الإلكتروني الحقيقي للمستخدم
            # للتسجيل والاختبار المحلي، يتم تسجيل الرابط في سجلات الخادم الآمنة فقط
            current_app.logger.info(f"Password reset link generated for user {user.email}: {reset_url}")
        
        # دائماً نظهر نفس الرسالة الأمنية بغض النظر عن وجود الحساب لمنع تخمين الإيميلات
        flash('✅ إذا كان البريد الإلكتروني مسجلاً لدينا، فقد تم إرسال تعليمات استعادة كلمة المرور إليه.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/reset_password_request.html', form=form)

@auth_bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        user_id = s.loads(token, salt='password-reset', max_age=3600)
    except:
        flash('❌ الرابط غير صالح أو انتهت صلاحيته.', 'danger')
        return redirect(url_for('auth.reset_password_request'))
    user = User.query.get(user_id)
    if not user:
        flash('❌ المستخدم غير موجود.', 'danger')
        return redirect(url_for('auth.reset_password_request'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        log_user_activity(user.id, "password_change")
        db.session.commit()
        flash('✅ تم تغيير كلمة المرور بنجاح.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/reset_password.html', form=form)
