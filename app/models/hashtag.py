from app.extensions import db
from datetime import datetime

class Hashtag(db.Model):
    __tablename__ = 'hashtags'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    posts = db.relationship('PostHashtag', backref='hashtag', lazy='dynamic', cascade='all, delete-orphan')
    
    def post_count(self):
        return self.posts.count()
    
    def __repr__(self):
        return f'#{self.name}'
