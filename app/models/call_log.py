from datetime import datetime

from app.extensions import db


class CallLog(db.Model):
    """سجل وصفي لمكالمة صوتية؛ لا يحتوي مطلقاً على صوت أو نص المكالمة."""

    __tablename__ = 'call_logs'

    id = db.Column(db.Integer, primary_key=True)
    call_id = db.Column(db.String(64), nullable=False, unique=True, index=True)
    caller_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    # ringing | answered | declined | missed | cancelled
    status = db.Column(db.String(20), nullable=False, default='ringing', index=True)
    started_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    answered_at = db.Column(db.DateTime, nullable=True)
    ended_at = db.Column(db.DateTime, nullable=True)
    duration_seconds = db.Column(db.Integer, nullable=True)

    caller = db.relationship('User', foreign_keys=[caller_id])
    receiver = db.relationship('User', foreign_keys=[receiver_id])

    def involves(self, user_id):
        return user_id in {self.caller_id, self.receiver_id}

    def __repr__(self):
        return f'<CallLog {self.call_id} {self.status}>'
