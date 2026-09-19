from app.extensions import db
from datetime import datetime

class VideoComment(db.Model):
    __tablename__ = 'video_comments'

    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    video_id = db.Column(db.Integer, db.ForeignKey('videos.id'), nullable=False, index=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('video_comments.id'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # ANTER: مؤشر "تم التعديل"
    edited_at = db.Column(db.DateTime, nullable=True)

    author = db.relationship('User', backref=db.backref('video_comments', lazy='dynamic', cascade='all, delete-orphan'))
    replies = db.relationship('VideoComment', backref=db.backref('parent', remote_side=[id]), lazy='dynamic')
    likes = db.relationship('VideoCommentLike', backref='comment', lazy='dynamic', cascade='all, delete-orphan')

    def like_count(self):
        return self.likes.count()

    def __repr__(self):
        return f'<VideoComment {self.id}>'
