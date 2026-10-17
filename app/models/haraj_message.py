"""ANTER Haraj: رسائل الحراج — منفصلة عن رسائل ANTER الأساسية."""

from datetime import datetime
from app.extensions import db


class HarajMessage(db.Model):
    __tablename__ = 'haraj_messages'

    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(
        db.Integer,
        db.ForeignKey('haraj_listings.id', ondelete='CASCADE'),
        nullable=False, index=True,
    )
    sender_id = db.Column(
        db.Integer, db.ForeignKey('users.id'), nullable=False, index=True,
    )
    receiver_id = db.Column(
        db.Integer, db.ForeignKey('users.id'), nullable=False, index=True,
    )
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(
        db.Boolean, nullable=False, default=False,
        server_default='false', index=True,
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    sender = db.relationship('User', foreign_keys=[sender_id])
    receiver = db.relationship('User', foreign_keys=[receiver_id])
    listing = db.relationship('Listing', foreign_keys=[listing_id])

    def __repr__(self):
        return f'<HarajMessage {self.id}>'
