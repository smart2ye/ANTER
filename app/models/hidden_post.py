from app.extensions import db
from datetime import datetime

class HiddenPost(db.Model):
    __tablename__ = 'hidden_posts'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('user_id', 'post_id', name='unique_hidden_post'),)

    def __repr__(self):
        return f'<HiddenPost {self.user_id}-{self.post_id}>'
