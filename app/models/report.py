from app.extensions import db
from datetime import datetime

class Report(db.Model):
    __tablename__ = 'reports'

    id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=True, index=True)
    comment_id = db.Column(db.Integer, db.ForeignKey('comments.id'), nullable=True, index=True)
    message_id = db.Column(db.Integer, db.ForeignKey('messages.id'), nullable=True, index=True)
    video_id = db.Column(db.Integer, db.ForeignKey('videos.id'), nullable=True, index=True)
    reason = db.Column(db.String(200), nullable=False)
    details = db.Column(db.Text, default='')
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime, nullable=True)
    resolved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    rejection_reason = db.Column(db.String(500), nullable=True)
    resolution_note = db.Column(db.Text, nullable=True)

    reporter = db.relationship('User', foreign_keys=[reporter_id])
    resolver = db.relationship('User', foreign_keys=[resolved_by])
    post = db.relationship('Post', backref='reports')
    comment = db.relationship('Comment', backref='reports')
    message = db.relationship('Message', backref='reports')
    video = db.relationship('Video', backref='reports')

    def __repr__(self):
        return f'<Report {self.id}>'
