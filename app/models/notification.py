from app.extensions import db
from datetime import datetime

class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    actor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    action = db.Column(db.String(50), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=True)
    comment_id = db.Column(db.Integer, db.ForeignKey('comments.id'), nullable=True, index=True)
    report_id = db.Column(db.Integer, db.ForeignKey('reports.id'), nullable=True, index=True)
    listing_id = db.Column(db.Integer, db.ForeignKey('haraj_listings.id', ondelete='CASCADE'), nullable=True, index=True)
    is_read = db.Column(db.Boolean, default=False, nullable=False, server_default='false', index=True)
    extra_text = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    actor = db.relationship('User', foreign_keys=[actor_id])
    post = db.relationship('Post', foreign_keys=[post_id])
    comment = db.relationship('Comment', foreign_keys=[comment_id])
    report = db.relationship('Report', foreign_keys=[report_id])
    listing = db.relationship('Listing', foreign_keys=[listing_id])

    def __repr__(self):
        return f'<Notification {self.id}>'
