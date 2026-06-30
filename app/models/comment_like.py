from app.extensions import db
from datetime import datetime

class CommentLike(db.Model):
    __tablename__ = 'comment_likes'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    comment_id = db.Column(db.Integer, db.ForeignKey('comments.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('user_id', 'comment_id', name='unique_comment_like'),)

    def __repr__(self):
        return f'<CommentLike {self.id}>'
