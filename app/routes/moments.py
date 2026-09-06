from flask import Blueprint, render_template
from flask_login import login_required

from app.models import Moment, MomentPost


moments_bp = Blueprint("moments", __name__, url_prefix="/moments")


@moments_bp.route("/")
@login_required
def index():
    moments = (
        Moment.query
        .filter_by(status="active")
        .order_by(Moment.updated_at.desc())
        .limit(30)
        .all()
    )

    return render_template("moments/index.html", moments=moments)

@moments_bp.route("/<int:moment_id>")
@login_required
def detail(moment_id):
    moment = (
        Moment.query
        .filter_by(id=moment_id, status="active")
        .first_or_404()
    )

    moment_posts = (
        MomentPost.query
        .filter_by(moment_id=moment.id)
        .join(MomentPost.post)
        .order_by(MomentPost.created_at.desc())
        .all()
    )

    posts = [link.post for link in moment_posts]

    return render_template(
        "moments/detail.html",
        moment=moment,
        posts=posts,
    )
