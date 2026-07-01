from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, SelectField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError, Regexp, Optional
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

class LoginForm(FlaskForm):
    username = StringField('اسم المستخدم أو البريد أو الهاتف', validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField('كلمة المرور', validators=[DataRequired()])
    remember_me = BooleanField('تذكرني')
    submit = SubmitField('دخول')

class RegistrationForm(FlaskForm):
    username = StringField('اسم المستخدم', validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField('البريد الإلكتروني', validators=[DataRequired(), Email()])
    name = StringField('الاسم الكامل', validators=[DataRequired(), Length(min=3, max=100)])
    
    # حقول الهاتف الجديدة
    country_code = SelectField('مفتاح الدولة', choices=COUNTRY_CODES, default='+966')
    phone = StringField('رقم الهاتف', validators=[
        Optional(),
        Length(min=6, max=15, message='يجب أن يكون رقم الهاتف بين 6 و 15 رقماً.')
    ])
    
    password = PasswordField('كلمة المرور', validators=[
        DataRequired(),
        Length(min=8, message='يجب أن تكون كلمة المرور 8 أحرف على الأقل.'),
        Regexp(
            r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$',
            message='يجب أن تحتوي كلمة المرور على: حرف كبير، حرف صغير، رقم، ورمز خاص (@$!%*?&).'
        )
    ])
    confirm_password = PasswordField('تأكيد كلمة المرور', validators=[DataRequired(), EqualTo('password')])
    terms_agreed = BooleanField('أوافق على الشروط والأحكام وسياسة الخصوصية', validators=[DataRequired(message='يجب الموافقة على الشروط والأحكام.')])
    submit = SubmitField('تسجيل')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data.strip()).first()
        if user:
            raise ValidationError('اسم المستخدم موجود بالفعل.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data.strip()).first()
        if user:
            raise ValidationError('البريد الإلكتروني مستخدم بالفعل.')

    def validate_phone(self, phone):
        if phone.data:
            if not re.match(r'^[0-9]+$', phone.data):
                raise ValidationError('يجب أن يحتوي رقم الهاتف على أرقام فقط.')
            full_phone = self.country_code.data + phone.data
            user = User.query.filter_by(phone=full_phone).first()
            if user:
                raise ValidationError('رقم الهاتف مستخدم بالفعل.')

    def validate_password(self, password):
        if not re.search(r'[A-Z]', password.data):
            raise ValidationError('يجب أن تحتوي كلمة المرور على حرف كبير واحد على الأقل.')
        if not re.search(r'[a-z]', password.data):
            raise ValidationError('يجب أن تحتوي كلمة المرور على حرف صغير واحد على الأقل.')
        if not re.search(r'\d', password.data):
            raise ValidationError('يجب أن تحتوي كلمة المرور على رقم واحد على الأقل.')
        if not re.search(r'[@$!%*?&]', password.data):
            raise ValidationError('يجب أن تحتوي كلمة المرور على رمز خاص واحد على الأقل (@$!%*?&).')

# ============================================
# نماذج إعادة تعيين كلمة المرور
# ============================================
class ResetPasswordRequestForm(FlaskForm):
    email = StringField('البريد الإلكتروني', validators=[DataRequired(), Email()])
    submit = SubmitField('إرسال رابط إعادة التعيين')

class ResetPasswordForm(FlaskForm):
    password = PasswordField('كلمة المرور الجديدة', validators=[
        DataRequired(),
        Length(min=8, message='يجب أن تكون كلمة المرور 8 أحرف على الأقل.'),
        Regexp(
            r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$',
            message='يجب أن تحتوي كلمة المرور على: حرف كبير، حرف صغير، رقم، ورمز خاص (@$!%*?&).'
        )
    ])
    confirm_password = PasswordField('تأكيد كلمة المرور', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('تغيير كلمة المرور')
