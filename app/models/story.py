from datetime import datetime
from app import db

class Story(db.Model):
    __tablename__ = 'story'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    media_url = db.Column(db.String(255))
    # ANTER: تخزين دائم للقصة في القاعدة
    media_data = db.Column(db.LargeBinary, nullable=True)
    media_mime = db.Column(db.String(100), nullable=True)
    media_type = db.Column(db.String(10), default='image')
    caption = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    is_active = db.Column(db.Boolean, default=True)

    # العلاقات
    user = db.relationship('User', backref=db.backref('stories', lazy='dynamic', cascade='all, delete-orphan'))
    views = db.relationship('StoryView', backref='story', lazy='dynamic', cascade='all, delete-orphan')
    reactions = db.relationship('StoryReaction', backref='story', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self, current_user_id=None):
        viewed = False
        if current_user_id:
            viewed = StoryView.query.filter_by(story_id=self.id, viewer_id=current_user_id).first() is not None

        viewers_list = []
        if current_user_id and self.user_id == current_user_id:
            for v in self.views.order_by(StoryView.viewed_at.desc()).all():
                if v.viewer:
                    viewers_list.append({
                        'id': v.viewer.id,
                        'name': v.viewer.name,
                        'username': v.viewer.username,
                        'avatar': v.viewer.avatar,
                        'viewed_at': v.viewed_at.strftime('%H:%M · %d/%m')
                    })

        reactions_data = {}
        for r in self.reactions.all():
            reactions_data[r.reaction_type] = reactions_data.get(r.reaction_type, 0) + 1

        user_reaction = None
        if current_user_id:
            ur = self.reactions.filter_by(user_id=current_user_id).first()
            if ur:
                user_reaction = ur.reaction_type

        return {
            'id': self.id,
            'user_id': self.user_id,
            'media_url': self.media_url,
            'media_type': self.media_type,
            'caption': self.caption or '',
            'created_at': self.created_at.isoformat() + 'Z',
            'expires_at': self.expires_at.isoformat() + 'Z',
            'views_count': self.views.count(),
            'viewed': viewed,
            'viewers': viewers_list,
            'reactions_count': self.reactions.count(),
            'reactions': reactions_data,
            'user_reaction': user_reaction,
            'is_owner': current_user_id == self.user_id if current_user_id else False
        }


class StoryView(db.Model):
    __tablename__ = 'story_view'
    
    id = db.Column(db.Integer, primary_key=True)
    story_id = db.Column(db.Integer, db.ForeignKey('story.id', ondelete='CASCADE'), nullable=False)
    viewer_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    viewed_at = db.Column(db.DateTime, default=datetime.utcnow)

    viewer = db.relationship('User', backref=db.backref('story_views', lazy='dynamic', cascade='all, delete-orphan'))

    __table_args__ = (db.UniqueConstraint('story_id', 'viewer_id', name='unique_story_viewer'),)


class StoryReaction(db.Model):
    __tablename__ = 'story_reaction'

    id = db.Column(db.Integer, primary_key=True)
    story_id = db.Column(db.Integer, db.ForeignKey('story.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    reaction_type = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('story_reactions', lazy='dynamic', cascade='all, delete-orphan'))

    __table_args__ = (db.UniqueConstraint('story_id', 'user_id', name='unique_story_user_reaction'),)
