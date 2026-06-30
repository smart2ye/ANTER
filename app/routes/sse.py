from flask import Blueprint, Response, stream_with_context, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Notification
import time
import json

sse_bp = Blueprint('sse', __name__, url_prefix='/sse')

@sse_bp.route('/notifications')
@login_required
def notifications_stream():
    def event_stream():
        last_count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
        while True:
            time.sleep(30)  # التحقق كل 3 ثوانٍ
            new_count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
            if new_count != last_count:
                last_count = new_count
                yield f"data: {json.dumps({'count': new_count})}\n\n"
    return Response(stream_with_context(event_stream()), mimetype="text/event-stream")
