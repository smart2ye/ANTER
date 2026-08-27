from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Length, ValidationError
from app.utils.profile_text import BIO_MAX_LENGTH, normalize_bio


def validate_profile_bio(form, field):
    if len(normalize_bio(field.data)) > BIO_MAX_LENGTH:
        raise ValidationError(f'السيرة الذاتية يجب ألا تتجاوز {BIO_MAX_LENGTH} حرفاً.')

class ProfileForm(FlaskForm):
    name = StringField('الاسم الكامل', validators=[DataRequired(), Length(min=3, max=100)])
    bio = TextAreaField('السيرة الذاتية', validators=[validate_profile_bio])
    avatar = FileField('صورة الملف الشخصي', validators=[FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'الصور فقط')])
    submit = SubmitField('حفظ التغييرات')
