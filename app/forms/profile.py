from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Length

class ProfileForm(FlaskForm):
    name = StringField('الاسم الكامل', validators=[DataRequired(), Length(min=3, max=100)])
    bio = TextAreaField('السيرة الذاتية', validators=[Length(max=200)])
    avatar = FileField('صورة الملف الشخصي', validators=[FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'الصور فقط')])
    submit = SubmitField('حفظ التغييرات')
