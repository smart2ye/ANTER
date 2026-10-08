from datetime import date

from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, TextAreaField, SubmitField, SelectField
from wtforms.fields import DateField
from wtforms.validators import DataRequired, Length, ValidationError, Optional
from app.utils.profile_text import BIO_MAX_LENGTH, normalize_bio
from app.forms.auth import COUNTRY_CODES, GENDER_CHOICES


def validate_profile_bio(form, field):
    if len(normalize_bio(field.data)) > BIO_MAX_LENGTH:
        raise ValidationError(f'السيرة الذاتية يجب ألا تتجاوز {BIO_MAX_LENGTH} حرفاً.')

class ProfileForm(FlaskForm):
    name = StringField('الاسم الكامل', validators=[DataRequired(), Length(min=3, max=100)])
    gender = SelectField('الجنس', choices=GENDER_CHOICES, validators=[Optional()])
    birth_date = DateField('تاريخ الميلاد', format='%d/%m/%Y', validators=[Optional()])
    country_code = SelectField('مفتاح الدولة', choices=COUNTRY_CODES, default='+967', validators=[Optional()])
    bio = TextAreaField('السيرة الذاتية', validators=[validate_profile_bio])
    avatar = FileField('صورة الملف الشخصي', validators=[FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'الصور فقط')])
    submit = SubmitField('حفظ التغييرات')

    def validate_birth_date(self, birth_date):
        if not birth_date.data:
            return
        today = date.today()
        birth = birth_date.data
        if birth > today:
            raise ValidationError('تاريخ الميلاد لا يمكن أن يكون في المستقبل.')
        age = today.year - birth.year - (
            (today.month, today.day) < (birth.month, birth.day)
        )
        if age < 13:
            raise ValidationError('يجب أن يكون عمرك 13 سنة أو أكثر.')
