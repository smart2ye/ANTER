"""صفحة الحصاد السنوي — بطاقة PNG قابلة للتحميل والمشاركة."""
from datetime import datetime
from io import BytesIO

from flask import Blueprint, render_template, send_file, abort, current_app
from flask_login import login_required, current_user

from app.services.year_in_review import collect
from app.services.year_card import render

year_in_review_bp = Blueprint('year_in_review', __name__)


def _year_or_default(year):
    current_year = datetime.utcnow().year
    if year is None:
        return current_year
    if year < 2020 or year > current_year:
        abort(404)
    return year


@year_in_review_bp.route('/year-in-review')
@year_in_review_bp.route('/year-in-review/<int:year>')
@login_required
def show(year=None):
    y = _year_or_default(year)
    payload = collect(current_user.id, y)
    return render_template('year_in_review.html', payload=payload, year=y)


@year_in_review_bp.route('/year-in-review/<int:year>/card.png')
@login_required
def card(year):
    y = _year_or_default(year)
    payload = collect(current_user.id, y)
    png = render(payload)
    return send_file(
        BytesIO(png),
        mimetype='image/png',
        as_attachment=False,
        download_name=f'anter-{current_user.username}-{y}.png',
        max_age=300,
    )
