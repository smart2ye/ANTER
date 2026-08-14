from datetime import datetime

from app.extensions import db


class TypingState(db.Model):
    """Short-lived typing state for one sender/receiver pair."""

    __tablename__ = 'typing_states'

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('sender_id', 'receiver_id', name='unique_typing_state'),
    )
