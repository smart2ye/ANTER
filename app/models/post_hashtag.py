from app.extensions import db
from datetime import datetime

class PostHashtag(db.Model):
    __tablename__ = 'post_hashtags'
    
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False, index=True)
    hashtag_id = db.Column(db.Integer, db.ForeignKey('hashtags.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('post_id', 'hashtag_id', name='unique_post_hashtag'),)
    
    def __repr__(self):
        return f'<PostHashtag {self.post_id}-{self.hashtag_id}>'
