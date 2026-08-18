from flask_wtf import FlaskForm
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
    ('', 'أفضل عدم التحديد'),
    ('male', 'ذكر'),
    ('female', 'أنثى'),
]


class LoginForm(FlaskForm):
    username = StringField('رقم الجوال أو البريد الإلكتروني أو المعرف', validators=[DataRequired(), Length(min=3, max=120)])
    password = PasswordField('كلمة المرور', validators=[DataRequired()])
    remember_me = BooleanField('تذكرني')
    submit = SubmitField('دخول')


class RegistrationForm(FlaskForm):
    name = StringField('الاسم الكامل', validators=[DataRequired(), Length(min=2, max=100)])
    gender = SelectField('الجنس', choices=GENDER_CHOICES, validators=[Optional()])
    birth_date = DateField('تاريخ الميلاد', format='%Y-%m-%d', validators=[Optional()])
    country_code = SelectField('مفتاح الدولة', choices=COUNTRY_CODES, default='+967')
    phone = StringField('رقم الجوال', validators=[Optional(), Length(min=6, max=15, message='رقم الجوال يجب أن يكون بين 6 و15 رقماً.')])
    email = StringField('البريد الإلكتروني', validators=[Optional(), Email(message='اكتب بريداً إلكترونياً صحيحاً.')])
    password = PasswordField('كلمة المرور', validators=[DataRequired(), Length(min=4, message='اكتب كلمة مرور من 4 أحرف أو أرقام على الأقل.')])
    confirm_password = PasswordField('إعادة تأكيد كلمة المرور', validators=[DataRequired(), EqualTo('password', message='كلمتا المرور غير متطابقتين.')])
    terms_agreed = BooleanField('أوافق على الشروط والأحكام وسياسة الخصوصية', validators=[DataRequired(message='يجب الموافقة على الشروط والأحكام.')])
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
        if value and User.query.filter_by(email=value).first():
            raise ValidationError('البريد الإلكتروني مستخدم بالفعل.')

    def validate_phone(self, phone):
        value = (phone.data or '').strip()
        if value:
            if not re.fullmatch(r'[0-9]+', value):
                raise ValidationError('رقم الجوال يجب أن يحتوي أرقاماً فقط.')
            full_phone = self.country_code.data + value
            if User.query.filter_by(phone=full_phone).first():
                raise ValidationError('رقم الجوال مستخدم بالفعل.')


# ============================================
# نماذج إعادة تعيين كلمة المرور
# ============================================
class ResetPasswordRequestForm(FlaskForm):
    email = StringField('البريد الإلكتروني', validators=[DataRequired(), Email()])
    submit = SubmitField('إرسال رابط إعادة التعيين')


class ResetPasswordForm(FlaskForm):
    password = PasswordField('كلمة المرور الجديدة', validators=[
        DataRequired(),
        Length(min=4, message='اكتب كلمة مرور من 4 أحرف أو أرقام على الأقل.')
    ])
    confirm_password = PasswordField('تأكيد كلمة المرور', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('تغيير كلمة المرور')
