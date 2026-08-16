from datetime import datetime
from app import db

class Story(db.Model):
    __tablename__ = 'story'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    media_url = db.Column(db.String(255))          # رابط الصورة أو الفيديو
    media_type = db.Column(db.String(10), default='image') # 'image' أو 'video'
    caption = db.Column(db.String(200))            # نص اختياري
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)            # تنتهي بعد 24 ساعة
    is_active = db.Column(db.Boolean, default=True)

    # العلاقات
    user = db.relationship('User', backref=db.backref('stories', lazy='dynamic', cascade='all, delete-orphan'))
    views = db.relationship('StoryView', backref='story', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self, current_user_id=None):
        viewed = False
        if current_user_id:
            viewed = StoryView.query.filter_by(story_id=self.id, viewer_id=current_user_id).first() is not None
        return {
            'id': self.id,
            'user_id': self.user_id,
            'media_url': self.media_url,
            'media_type': self.media_type,
            'caption': self.caption or '',
            'created_at': self.created_at.isoformat() + 'Z',
            'expires_at': self.expires_at.isoformat() + 'Z',
            'views_count': self.views.count(),
            'viewed': viewed
        }


class StoryView(db.Model):
    __tablename__ = 'story_view'
    
    id = db.Column(db.Integer, primary_key=True)
    story_id = db.Column(db.Integer, db.ForeignKey('story.id', ondelete='CASCADE'), nullable=False)
    viewer_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    viewed_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('story_id', 'viewer_id', name='unique_story_viewer'),)
