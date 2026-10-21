from flask_wtf import FlaskForm
from datetime import date
from wtforms import StringField, PasswordField, SubmitField, BooleanField, SelectField
from wtforms.fields import DateField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError, Optional
from app.models import User
import re

# قائمة مفاتيح الدول العربية والعالمية
COUNTRY_CODES = [
    ('+20', '🇪🇬 مصر +20'),
    ('+966', '🇸🇦 السعودية +966'),
    ('+971', '🇦🇪 الإمارات +971'),
    ('+965', '🇰🇼 الكويت +965'),
    ('+974', '🇶🇦 قطر +974'),
    ('+968', '🇴🇲 عمان +968'),
    ('+973', '🇧🇭 البحرين +973'),
    ('+967', '🇾🇪 اليمن +967'),
    ('+962', '🇯🇴 الأردن +962'),
    ('+961', '🇱🇧 لبنان +961'),
    ('+963', '🇸🇾 سوريا +963'),
    ('+970', '🇵🇸 فلسطين +970'),
    ('+964', '🇮🇶 العراق +964'),
    ('+218', '🇱🇾 ليبيا +218'),
    ('+216', '🇹🇳 تونس +216'),
    ('+213', '🇩🇿 الجزائر +213'),
    ('+212', '🇲🇦 المغرب +212'),
    ('+222', '🇲🇷 موريتانيا +222'),
    ('+252', '🇸🇴 الصومال +252'),
    ('+253', '🇩🇯 جيبوتي +253'),
    ('+249', '🇸🇩 السودان +249'),
    ('+90', '🇹🇷 تركيا +90'),
    ('+1', '🇺🇸 الولايات المتحدة +1'),
    ('+44', '🇬🇧 المملكة المتحدة +44'),
    ('+33', '🇫🇷 فرنسا +33'),
    ('+49', '🇩🇪 ألمانيا +49'),
    ('+39', '🇮🇹 إيطاليا +39'),
    ('+34', '🇪🇸 إسبانيا +34'),
    ('+61', '🇦🇺 أستراليا +61'),
    ('+81', '🇯🇵 اليابان +81'),
    ('+86', '🇨🇳 الصين +86'),
    ('+91', '🇮🇳 الهند +91'),
]

GENDER_CHOICES = [
    ('', 'اختر الجنس'),
    ('male', 'ذكر'),
    ('female', 'أنثى'),
]


# ============================================================
# ANTER: نطاقات بريد محظورة (نطاقات مزيفة تُستخدم في التسجيل الآلي)
# ============================================================
BLOCKED_EMAIL_DOMAINS = {
    # Gmail مزيف
    'gmail10p.com', 'gmail10p.net', 'gmail10p.org',
    # نطاقات بريد مؤقت شائعة
    'temp-mail.org', 'tempmail.com', 'tempmail.net',
    'guerrillamail.com', 'guerrillamail.net', 'guerrillamail.org',
    '10minutemail.com', '10minutemail.net',
    'yopmail.com', 'yopmail.fr', 'yopmail.net',
    'mailinator.com', 'mailinator.net',
    'sharklasers.com', 'guerrillamailblock.com', 'grr.la',
    'dispostable.com', 'trashmail.com', 'throwawaymail.com',
    'getnada.com', 'tempr.email', 'fakeinbox.com',
    'spam4.me', 'mytemp.email', 'mohmal.com',
    'maildrop.cc', 'inboxbear.com', 'mailcatch.com',
    'mintemail.com', 'spambog.com', 'wegwerfmail.de',
}


class LoginForm(FlaskForm):
    username = StringField('رقم الجوال أو البريد الإلكتروني أو المعرف', validators=[DataRequired(), Length(min=3, max=120)])
    password = PasswordField('كلمة المرور', validators=[DataRequired()])
    remember_me = BooleanField('تذكرني')
    submit = SubmitField('دخول')


class RegistrationForm(FlaskForm):
    name = StringField('الاسم الكامل', validators=[DataRequired(), Length(min=2, max=100)])
    country_code = SelectField('مفتاح الدولة', choices=COUNTRY_CODES, default='+967', validators=[Optional()])
    phone = StringField('رقم الجوال', validators=[Optional(), Length(min=6, max=15, message='رقم الجوال يجب أن يكون بين 6 و15 رقماً.')])
    email = StringField('البريد الإلكتروني', validators=[Optional(), Email(message='اكتب بريداً إلكترونياً صحيحاً.')])
    password = PasswordField('كلمة المرور', validators=[DataRequired(), Length(min=8, message='كلمة المرور يجب أن تكون 8 أحرف على الأقل.')])
    submit = SubmitField('إنشاء الحساب')

    def validate(self, extra_validators=None):
        valid = super().validate(extra_validators=extra_validators)
        email = (self.email.data or '').strip()
        phone = (self.phone.data or '').strip()
        if not email and not phone:
            message = 'أدخل رقم الجوال أو البريد الإلكتروني على الأقل لتسجيل الدخول لاحقاً.'
            self.phone.errors.append(message)
            self.email.errors.append(message)
            return False
        return valid

    def validate_email(self, email):
        value = (email.data or '').strip().lower()
        if not value:
            return

        # رفض النطاقات المزيفة أو خدمات البريد المؤقت.
        if '@' in value:
            domain = value.rsplit('@', 1)[1].strip().lower()
            if domain in BLOCKED_EMAIL_DOMAINS:
                raise ValidationError('هذا النطاق غير مدعوم. استخدم بريداً حقيقياً.')

        existing = User.query.filter_by(email=value).first()
        if existing:
            if getattr(existing, 'is_deleted', False):
                raise ValidationError('هذا الحساب محذوف. لا يمكن التسجيل بنفس البريد.')
            raise ValidationError('البريد الإلكتروني مستخدم بالفعل.')

    def validate_phone(self, phone):
        value = (phone.data or '').strip()
        if not value:
            return
        if not re.fullmatch(r'[0-9]+', value):
            raise ValidationError('رقم الجوال يجب أن يحتوي أرقاماً فقط.')

        # إزالة الصفر في البداية (خطأ شائع) — إن وُجد
        if value.startswith('0'):
            value = value.lstrip('0')

        cc = (self.country_code.data or '').strip()
        required_length = None
        required_prefix = None

        # قواعد لكل دولة
        if cc == '+966':
            required_length = 9
            required_prefix = '5'
        elif cc == '+967':
            required_length = 9
            required_prefix = '7'

        if required_length is not None:
            if len(value) != required_length:
                raise ValidationError(
                    f'رقم الجوال لهذا البلد يجب أن يتكون من {required_length} أرقام (بدون الصفر في البداية).'
                )
            if required_prefix and not value.startswith(required_prefix):
                raise ValidationError(
                    f'رقم الجوال لهذا البلد يجب أن يبدأ بالرقم {required_prefix}.'
                )
        else:
            # قواعد عامة للدول الأخرى
            if not (6 <= len(value) <= 15):
                raise ValidationError('رقم الجوال يجب أن يكون بين 6 و15 رقماً.')

        # حفظ القيمة المُنظَّفة ليُستخدم في التسجيل لاحقًا
        self.phone.data = value

        full_phone = cc + value
        existing = User.query.filter_by(phone=full_phone).first()
        if existing:
            if getattr(existing, 'is_deleted', False):
                raise ValidationError('هذا الحساب محذوف. لا يمكن التسجيل بنفس الرقم.')
            raise ValidationError('رقم الجوال مستخدم بالفعل.')

    def validate_password(self, password):
        value = password.data or ''
        if not value:
            return
        # ANTER: كلمة المرور يجب أن تحتوي حرفاً ورقماً على الأقل.
        has_letter = re.search(r'[a-zA-Z\u0600-\u06FF]', value) is not None
        has_digit = re.search(r'\d', value) is not None
        if not has_letter or not has_digit:
            raise ValidationError('كلمة المرور يجب أن تحتوي على حرف ورقم على الأقل.')


# ============================================
# نماذج إعادة تعيين كلمة المرور
# ============================================
class ResetPasswordRequestForm(FlaskForm):
    email = StringField('البريد الإلكتروني', validators=[DataRequired(), Email()])
    submit = SubmitField('إرسال رابط إعادة التعيين')


class ResetPasswordForm(FlaskForm):
    identity = StringField(
        'اسم المستخدم أو البريد أو رقم الجوال',
        validators=[DataRequired(), Length(min=3, max=120)],
        description='أكّد هويتك بكتابة اسم المستخدم أو البريد أو رقم الجوال المرتبط بالحساب.',
    )
    password = PasswordField('كلمة المرور الجديدة', validators=[
        DataRequired(),
        Length(min=4, message='اكتب كلمة مرور من 4 أحرف أو أرقام على الأقل.')
    ])
    confirm_password = PasswordField('تأكيد كلمة المرور', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('تغيير كلمة المرور')
