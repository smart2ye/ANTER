from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import TextAreaField, SubmitField
from wtforms.validators import DataRequired, Length

class PostForm(FlaskForm):
    content = TextAreaField('المحتوى', validators=[DataRequired(), Length(min=1, max=2000)])
    image = FileField('صورة', validators=[FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'الصور فقط')])
    submit = SubmitField('نشر')
