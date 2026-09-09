from app.extensions import db
from datetime import datetime
from app.utils.public_ids import generate_public_id

class Video(db.Model):
    __tablename__ = 'videos'

    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(40), unique=True, nullable=False, default=lambda: generate_public_id('r'))
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default='')
    file_path = db.Column(db.String(300), nullable=False)
    thumbnail_path = db.Column(db.String(300), default='default_thumb.png')
    duration = db.Column(db.Integer, default=0)
    views = db.Column(db.Integer, default=0)
    shares = db.Column(db.Integer, default=0)
    is_reel = db.Column(db.Boolean, default=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    author = db.relationship('User', backref=db.backref('videos', lazy='dynamic', cascade='all, delete-orphan'))
    likes = db.relationship('VideoLike', backref='video', lazy='dynamic', cascade='all, delete-orphan')
    comments = db.relationship('VideoComment', backref='video', lazy='dynamic', cascade='all, delete-orphan')

    def like_count(self):
        return self.likes.count()

    def comment_count(self):
        return self.comments.count()

    def __repr__(self):
        return f'<Video {self.id}>'
