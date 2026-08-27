from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional


SUPPORT_TOPIC_CHOICES = [
    ('login', 'تسجيل الدخول'),
    ('password', 'كلمة المرور'),
    ('account', 'الحساب والملف الشخصي'),
    ('technical', 'مشكلة تقنية'),
    ('report', 'إبلاغ عن محتوى أو مستخدم'),
    ('other', 'مشكلة أخرى'),
]


class SupportRequestForm(FlaskForm):
    topic = SelectField('نوع المشكلة', choices=SUPPORT_TOPIC_CHOICES, validators=[DataRequired()])
    contact = StringField(
        'وسيلة التواصل (اختياري)',
        validators=[Optional(), Length(max=120, message='وسيلة التواصل طويلة جداً.')],
        description='بريدك أو رقم جوالك إن رغبت في تلقي رد.',
    )
    message = TextAreaField(
        'صف المشكلة',
        validators=[DataRequired(message='اكتب وصفاً للمشكلة.'), Length(min=10, max=2000)],
    )
    submit = SubmitField('إرسال طلب المساعدة')
