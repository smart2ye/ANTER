"""نماذج Haraj: نشر وتعديل الإعلانات."""

from flask_wtf import FlaskForm
from wtforms import (
    StringField, TextAreaField, SelectField, IntegerField, BooleanField,
    MultipleFileField, SubmitField,
)
from wtforms.validators import (
    DataRequired, Length, NumberRange, Optional, ValidationError,
)
from flask_wtf.file import FileAllowed

from app.models.listing import (
    LISTING_CATEGORIES, LISTING_TYPES, LISTING_CONDITIONS,
    LISTING_SUBCATEGORIES,
)
from app.constants.saudi_locations import SAUDI_REGIONS, YEMEN_REGIONS, all_regions


class ListingForm(FlaskForm):
    category = SelectField(
        'الفئة',
        choices=[(k, v) for k, v in LISTING_CATEGORIES.items()],
        validators=[DataRequired('اختر الفئة')],
    )
    subcategory = SelectField(
        'الفئة الفرعية',
        choices=[('', 'اختر الفئة الفرعية')],
        validators=[DataRequired('اختر الفئة الفرعية')],
    )

    listing_type = SelectField(
        'نوع الإعلان',
        choices=[(k, v) for k, v in LISTING_TYPES.items()],
        validators=[DataRequired()],
    )
    condition = SelectField(
        'الحالة',
        choices=[(k, v) for k, v in LISTING_CONDITIONS.items()],
        validators=[DataRequired()],
    )
    title = StringField(
        'العنوان',
        validators=[
            DataRequired('العنوان مطلوب'),
            Length(min=5, max=120, message='العنوان بين 5 و120 حرفًا'),
        ],
    )
    description = TextAreaField(
        'الوصف',
        validators=[
            DataRequired('الوصف مطلوب'),
            Length(min=10, max=2000, message='الوصف بين 10 و2000 حرف'),
        ],
    )
    price = IntegerField(
        'السعر (ريال)',
        validators=[
            Optional(),
            NumberRange(min=0, max=10000000, message='السعر غير صالح'),
        ],
    )
    negotiable = BooleanField('قابل للتفاوض')

    region = SelectField(
        'المنطقة',
        choices=[(r, r) for r in all_regions()],
        validators=[DataRequired('اختر المنطقة')],
    )
    city = SelectField(
        'المدينة',
        choices=[('', 'اختر المدينة')],
        validators=[DataRequired('اختر المدينة')],
    )

    show_whatsapp = BooleanField('إظهار رقم الواتساب')

    images = MultipleFileField(
        'الصور (3 صور كحد أقصى)',
        validators=[FileAllowed(['jpg', 'jpeg', 'png', 'webp'], 'صور فقط: JPG، PNG، WebP')],
    )

    pledge_accepted = BooleanField(
        'أتعهد بدفع 1% لموقع أنتر',
        validators=[DataRequired('يجب الموافقة على التعهد للنشر')],
    )

    submit = SubmitField('نشر الإعلان')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # تعبئة الفئات الفرعية حسب الفئة
        if self.category.data and self.category.data in LISTING_SUBCATEGORIES:
            subs = LISTING_SUBCATEGORIES[self.category.data]
            self.subcategory.choices = [('', 'اختر الفئة الفرعية')] + [(k, v) for k, v in subs.items()]
        # تعبئة المدن حسب المنطقة (سعودية أو يمنية)
        _region_map = {}
        _region_map.update(SAUDI_REGIONS)
        _region_map.update(YEMEN_REGIONS)
        if self.region.data and self.region.data in _region_map:
            cities = [(c, c) for c in _region_map[self.region.data]]
            self.city.choices = [('', 'اختر المدينة')] + cities
