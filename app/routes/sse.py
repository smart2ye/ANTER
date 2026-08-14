from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from app.models import Notification

sse_bp = Blueprint('sse', __name__, url_prefix='/sse')


@sse_bp.route('/notifications')
@login_required
def notifications_stream():
    """Return a short-lived notification snapshot.

    The previous implementation kept a worker occupied in an infinite SSE
    loop. That caused Gunicorn worker timeouts on Render's free service. The
    frontend now polls this endpoint periodically, so every request returns
    immediately and remains compatible with SQLite and PostgreSQL.
    """
    count = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False,
    ).count()
    return jsonify({'count': count})
