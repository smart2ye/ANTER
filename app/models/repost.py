from app.extensions import db
from datetime import datetime

class Repost(db.Model):
    __tablename__ = 'reposts'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('user_id', 'post_id', name='unique_repost'),)

    user = db.relationship('User', backref='reposts')
    post = db.relationship('Post', backref='reposts')

    def __repr__(self):
        return f'<Repost {self.id}>'
