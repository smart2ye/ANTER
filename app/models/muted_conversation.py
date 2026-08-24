from datetime import datetime

from app.extensions import db


class MutedConversation(db.Model):
    """إعداد شخصي لكتم محادثة من دون منع الرسائل أو حذفها."""

    __tablename__ = 'muted_conversations'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    muted_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'muted_user_id', name='unique_muted_conversation'),
    )

