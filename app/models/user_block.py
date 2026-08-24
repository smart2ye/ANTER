from datetime import datetime

from app.extensions import db


class UserBlock(db.Model):
    """علاقة حظر أحادية الاتجاه؛ يمنع الحظر التفاعل الخاص في الاتجاهين."""

    __tablename__ = 'user_blocks'

    id = db.Column(db.Integer, primary_key=True)
    blocker_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    blocked_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('blocker_id', 'blocked_id', name='unique_user_block'),
    )

