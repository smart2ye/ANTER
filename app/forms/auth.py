from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError, Regexp
from app.models import User
import re

class LoginForm(FlaskForm):
    username = StringField('اسم المستخدم', validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField('كلمة المرور', validators=[DataRequired()])
    remember_me = BooleanField('تذكرني')
    submit = SubmitField('دخول')

class RegistrationForm(FlaskForm):
    username = StringField('اسم المستخدم', validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField('البريد الإلكتروني', validators=[DataRequired(), Email()])
    name = StringField('الاسم الكامل', validators=[DataRequired(), Length(min=3, max=100)])
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

    def validate_password(self, password):
        if not re.search(r'[A-Z]', password.data):
            raise ValidationError('يجب أن تحتوي كلمة المرور على حرف كبير واحد على الأقل.')
        if not re.search(r'[a-z]', password.data):
            raise ValidationError('يجب أن تحتوي كلمة المرور على حرف صغير واحد على الأقل.')
        if not re.search(r'\d', password.data):
            raise ValidationError('يجب أن تحتوي كلمة المرور على رقم واحد على الأقل.')
        if not re.search(r'[@$!%*?&]', password.data):
            raise ValidationError('يجب أن تحتوي كلمة المرور على رمز خاص واحد على الأقل (@$!%*?&).')

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
