from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl

from flask import Blueprint, abort, render_template, redirect, url_for, flash, request, current_app, session
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db, csrf
from app.models import User
from app.forms.auth import LoginForm, RegistrationForm, ResetPasswordRequestForm, ResetPasswordForm
from itsdangerous import URLSafeTimedSerializer
from app.utils.helpers import log_user_activity
from app.utils.email import send_reset_email, send_welcome_email
from app.services.anter_assistant import ensure_anter_assistant_user, follow_anter_assistant_for_user
from app.services.anter_user_messages import send_welcome_message
from app.services.account_vault import (
    add_account as vault_add,
    clear_accounts as vault_clear,
    enrich_accounts as vault_enrich,
    get_saved_accounts as vault_list,
    remove_account as vault_remove,
    resolve_switch_token as vault_resolve,
)
from app.services.anter_account_switching import (
    can_switch_back,
    can_switch_to_assistant,
    get_managed_assistant,
)
from app.utils.public_ids import generate_public_id
from app.services.mobile_api_auth import issue_mobile_browser_authorization

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


def _append_query_parameters(url, **parameters):
    parsed = urlsplit(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.update({key: value for key, value in parameters.items() if value is not None})
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))


@auth_bp.route('/messenger/authorize')
def messenger_authorize():
    """يعيد جلسة موقع ANTER إلى Messenger برمز تفويض قصير لا بكلمة مرور أو رمز وصول."""
    redirect_uri = (request.args.get('redirect_uri') or '').strip()
    state = (request.args.get('state') or '').strip()
    device_name = (request.args.get('device_name') or 'ANTER Messenger').strip()
    allowed_redirect_uri = current_app.config['MOBILE_BROWSER_AUTH_REDIRECT_URI']
    if redirect_uri != allowed_redirect_uri or not state or len(state) > 120:
        abort(400)

    if not current_user.is_authenticated:
        next_page = url_for(
            'auth.messenger_authorize',
            redirect_uri=redirect_uri,
            state=state,
            device_name=device_name,
        )
        return redirect(url_for('auth.login', next=next_page))

    code = issue_mobile_browser_authorization(current_user, state, redirect_uri, device_name)
    return redirect(_append_query_parameters(redirect_uri, code=code, state=state))

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = LoginForm()

    # الحسابات المحفوظة على هذا الجهاز (للعرض أسفل النموذج)
    saved_accounts = []
    try:
        raw = vault_list()
        if raw:
            saved_accounts = [a for a in vault_enrich(raw) if not a.get('is_current')]
    except Exception:
        current_app.logger.exception('تعذر تحميل الحسابات المحفوظة')
        saved_accounts = []
    if form.validate_on_submit():
        # البحث باستخدام اسم المستخدم أو البريد أو رقم الهاتف
        user = User.query.filter(
            (User.username == form.username.data) |
            (User.email == form.username.data) |
            (User.phone == form.username.data)
        ).first()
        if user and user.check_password(form.password.data):
            if getattr(user, 'is_deleted', False):
                flash('هذا الحساب محذوف. للاعتراض تواصل مع إدارة ANTER.', 'danger')
                return render_template('auth/login.html', form=form, saved_accounts=saved_accounts)
            if getattr(user, 'is_banned', False):
                flash('تم حظر حسابك. للاعتراض راسل إدارة ANTER.', 'danger')
                return render_template('auth/login.html', form=form, saved_accounts=saved_accounts)
            login_user(user, remember=True)
            log_user_activity(user.id, "login")
            session['play_welcome_chime'] = True
            next_page = request.args.get('next')
            flash('✅ تم تسجيل الدخول بنجاح!', 'success')
            resp = redirect(next_page or url_for('main.index'))
            # احفظ الحساب في كوكي الحسابات المتعددة (للتبديل السريع لاحقًا).
            try:
                vault_add(user, resp)
            except Exception:
                current_app.logger.exception('فشل حفظ الحساب في account_vault')
            return resp
        else:
            flash('❌ اسم المستخدم أو كلمة المرور غير صحيحة.', 'danger')
    return render_template('auth/login.html', form=form, saved_accounts=saved_accounts)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = RegistrationForm()
    submitted = form.validate_on_submit()
    if request.method == 'POST' and not submitted:
        current_app.logger.warning(
            "REGISTER VALIDATION FAILED | errors=%s | data=%s",
            form.errors,
            {
                "name": form.name.data,
                "country_code": form.country_code.data,
                "phone": form.phone.data,
                "email": form.email.data,
                "password_present": bool(form.password.data),
            },
        )

    if submitted:
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
        country_code = (form.country_code.data or '+967').strip()
        # ANTER: الجنس وتاريخ الميلاد ينتقلان لصفحة إكمال الملف بعد التسجيل.
        # ANTER: إحالة — أولوية: حقل النموذج (يدوي/تلقائي) → الجلسة (?ref=) → request.form
        ref_code = (form.ref.data or '').strip() or session.pop('referral_code', None) or (request.form.get('ref') or '').strip()
        session.pop('referral_code', None)  # تنظيف دائمًا
        referrer = None
        if ref_code:
            try:
                from app.services.referral import find_by_code
                referrer = find_by_code(ref_code)
            except Exception:
                referrer = None

        user = User(
            username=username,
            email=email,
            name=form.name.data.strip(),
            avatar='img/default_avatar_male.webp',
            country_code=country_code,
            phone=country_code + phone if phone else None,
            phone_verified=False,
            terms_agreed=True,
            referred_by_id=referrer.id if referrer else None,
        )
        user.set_password(form.password.data)
        assistant = ensure_anter_assistant_user()
        db.session.add(user)
        db.session.flush()
        follow_anter_assistant_for_user(user, assistant)
        send_welcome_message(user)
        db.session.commit()
        # ANTER: توليد كود الإحالة فورًا بعد الحفظ (لتفادي استعلام إضافي لاحقًا)
        try:
            from app.services.referral import get_or_create_referral_code
            get_or_create_referral_code(user)
        except Exception:
            current_app.logger.exception('referral code generation failed (non-fatal)')
        log_user_activity(user.id, 'registration')
        login_user(user, remember=True)
        session['play_welcome_chime'] = True

        # طلب تأكيد البريد تلقائياً عند التسجيل، حتى للأرقام بلا بريد حقيقي.
        # الأدمن سيولّد الرابط ويرسله للمستخدم عبر الوسيلة المتاحة (بريد، واتساب، ...).
        try:
            existing = Report.query.filter_by(
                reporter_id=user.id,
                reason='verification:email',
                status='pending',
            ).first()
            if not existing:
                contact_parts = []
                if email and not email.endswith('@phone-only.anter.local'):
                    contact_parts.append(f'البريد: {email}')
                if phone:
                    contact_parts.append(f'الجوال: {user.phone}')
                contact_info = ' | '.join(contact_parts) or 'لا توجد وسيلة تواصل مسجّلة'
                db.session.add(Report(
                    reporter_id=user.id,
                    reason='verification:email',
                    details=f'طلب تأكيد الحساب — {contact_info}',
                ))
                db.session.commit()
        except Exception:
            db.session.rollback()

        # البريد خدمة إضافية ولا يجب أن يمنع إنشاء الحساب
        send_welcome_email(user)
        # ANTER: علامة onboarding — بعد حفظ الملف الشخصي ننتقل لكتلة الترحيب.
        session['onboarding'] = True
        # ANTER: علامة onboarding — بعد حفظ الملف الشخصي ننتقل لكتلة الترحيب.
        session['onboarding'] = True
        flash('✅ تم إنشاء الحساب. أكمل ملفك الشخصي لتجربة أفضل.', 'success')
        return redirect(url_for('users.edit_profile'))
    # ANTER: إحالة — إذا وصل المستخدم عبر ?ref=CODE، نحفظه في الجلسة للاستخدام عند POST
    if request.method == 'GET':
        ref = (request.args.get('ref') or '').strip()
        if ref:
            session['referral_code'] = ref[:12]
        # تعبئة الحقل تلقائيًا من الجلسة (إن وُجد رمز سابق)
        if not form.ref.data and session.get('referral_code'):
            form.ref.data = session['referral_code']

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


@auth_bp.route('/switch-back-to-owner', methods=['GET', 'POST'])
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
    # نُبقي كوكي الحسابات المحفوظة كي يستطيع المستخدم التبديل بسرعة.
    return redirect(url_for('auth.login'))


# ============================================================
# تبديل الحساب — ميزة "حسابات متعددة" مثل إنستغرام/فيسبوك
# ============================================================
@auth_bp.route('/accounts')
def accounts_list():
    """صفحة إدارة الحسابات المحفوظة على هذا الجهاز."""
    raw = vault_list()
    accounts = vault_enrich(raw) if raw else []
    return render_template('auth/accounts.html', accounts=accounts)


@auth_bp.route('/switch', methods=['POST'])
@csrf.exempt
def accounts_switch():
    """يبدّل الجلسة الحالية إلى حساب محفوظ بدون كلمة سر."""
    token = (request.form.get('token') or '').strip()
    next_url = request.form.get('next') or url_for('main.index')
    if not token:
        flash('طلب غير صالح.', 'danger')
        return redirect(url_for('auth.accounts_list'))

    user = vault_resolve(token)
    if not user:
        flash('انتهت الجلسة. حاول تسجيل الدخول مرة أخرى.', 'warning')
        return redirect(url_for('auth.login'))

    # ANTER: حماية مزدوجة — لا تبديل لحساب محذوف أو معطّل.
    if getattr(user, 'is_deleted', False) or not getattr(user, 'is_active', True):
        flash('هذا الحساب محذوف أو معطّل.', 'danger')
        return redirect(url_for('auth.login'))

    # ANTER: منع open redirect — نقبل المسارات الداخلية فقط.
    if not next_url.startswith('/') or next_url.startswith('//'):
        next_url = url_for('main.index')

    # نُسجّل الدخول
    logout_user()
    login_user(user, remember=True, force=True)
    log_user_activity(user.id, 'switch_account')
    session['play_welcome_chime'] = True
    flash(f'✅ تم التبديل إلى {user.name or user.username}.', 'success')
    return redirect(next_url)


@auth_bp.route('/accounts/remove/<int:user_id>', methods=['POST'])
@csrf.exempt
def accounts_remove(user_id):
    """يُزيل حسابًا من القائمة المحفوظة."""
    resp = redirect(url_for('auth.accounts_list'))
    vault_remove(user_id, resp)
    flash('تمت إزالة الحساب من هذا الجهاز.', 'success')
    return resp


@auth_bp.route('/accounts/clear', methods=['POST'])
@csrf.exempt
def accounts_clear():
    """يمسح كل الحسابات المحفوظة."""
    resp = redirect(url_for('auth.accounts_list'))
    vault_clear(resp)
    flash('تم مسح كل الحسابات المحفوظة.', 'success')
    return resp

@auth_bp.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = ResetPasswordRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            from app.models import Report
            existing = Report.query.filter_by(
                reporter_id=user.id,
                reason='password-reset-request',
                status='pending',
            ).first()
            if not existing:
                req = Report(
                    reporter_id=user.id,
                    reason='password-reset-request',
                    details=f'طلب إعادة تعيين كلمة السر للبريد: {user.email}',
                )
                db.session.add(req)
                db.session.commit()
        
        # دائماً نظهر نفس الرسالة الأمنية بغض النظر عن وجود الحساب لمنع تخمين الإيميلات
        flash('✅ إذا كان البريد الإلكتروني مسجلاً لدينا، فقد تم إرسال تعليمات استعادة كلمة المرور إليه.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/reset_password_request.html', form=form)

@auth_bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    from app.services.password_reset import verify_token
    user = verify_token(token)
    if not user:
        # الرمز لاغٍ: منتهي، مستخدم، أو استُخدم من قبل (تغيّر password_hash).
        flash('❌ الرابط غير صالح أو انتهت صلاحيته.', 'danger')
        return redirect(url_for('auth.reset_password_request'))
    form = ResetPasswordForm()
    # تعبئة حقل الهوية تلقائيًا عند الدخول بالرابط (GET فقط)
    if request.method == 'GET' and not form.identity.data:
        if user.email and not user.email.endswith('@phone-only.anter.local'):
            form.identity.data = user.email
        elif user.phone:
            form.identity.data = user.phone
        else:
            form.identity.data = user.username
    if form.validate_on_submit():
        identity = (form.identity.data or '').strip().lower()
        user_username = (user.username or '').strip().lower()
        user_email = (user.email or '').strip().lower()

        def _phone_match(raw, phone):
            if not raw or not phone:
                return False
            a = ''.join(c for c in raw if c.isdigit())
            b = ''.join(c for c in phone if c.isdigit())
            if len(a) < 7 or not b:
                return False
            return b.endswith(a) or a.endswith(b)

        if identity not in (user_username, user_email) and not _phone_match(identity, user.phone):
            flash('❌ اسم المستخدم أو البريد أو رقم الجوال غير مطابق للحساب المرتبط بهذا الرابط.', 'danger')
            return render_template('auth/reset_password.html', form=form)
        user.set_password(form.password.data)
        log_user_activity(user.id, "password_change")
        db.session.commit()
        flash('✅ تم تغيير كلمة المرور بنجاح.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/reset_password.html', form=form)
