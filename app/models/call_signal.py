from datetime import datetime
from app.extensions import db


class CallSignal(db.Model):
    """إشارة قصيرة العمر تستخدم فقط لتنسيق مكالمات WebRTC الفردية."""

    __tablename__ = 'call_signals'

    id = db.Column(db.Integer, primary_key=True)
    call_id = db.Column(db.String(64), nullable=False, index=True)
    signal_type = db.Column(db.String(20), nullable=False)
    payload = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    delivered_at = db.Column(db.DateTime, nullable=True)

    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)

    sender = db.relationship('User', foreign_keys=[sender_id])
    receiver = db.relationship('User', foreign_keys=[receiver_id])

    def to_dict(self):
        return {
            'id': self.id,
            'callId': self.call_id,
            'type': self.signal_type,
            'payload': self.payload,
            'senderId': self.sender_id,
            'receiverId': self.receiver_id,
            'createdAt': self.created_at.isoformat(),
        }
