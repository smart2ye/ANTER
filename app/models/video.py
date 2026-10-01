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
    # ANTER: تخزين دائم في قاعدة البيانات (لا يُحذف عند إعادة نشر Render)
    video_data = db.Column(db.LargeBinary, nullable=True)
    video_mime = db.Column(db.String(100), nullable=True, default='video/mp4')
    thumbnail_path = db.Column(db.String(300), default='default_thumb.png')
    thumbnail_data = db.Column(db.LargeBinary, nullable=True)
    thumbnail_mime = db.Column(db.String(100), nullable=True, default='image/jpeg')
    duration = db.Column(db.Integer, default=0)
    views = db.Column(db.Integer, default=0)
    shares = db.Column(db.Integer, default=0)
    is_reel = db.Column(db.Boolean, default=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
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
