from app.extensions import db
from datetime import datetime
from app.utils.public_ids import generate_public_id

class Post(db.Model):
    __tablename__ = 'posts'

    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(40), unique=True, nullable=False, default=lambda: generate_public_id('p'))
    content = db.Column(db.Text, nullable=False)
    image = db.Column(db.String(200), default='')
    image_data = db.Column(db.LargeBinary, nullable=True)
    image_mime = db.Column(db.String(100), nullable=True)

    # حقول معاينة الرابط (Link Preview)
    link_url = db.Column(db.String(500), nullable=True)
    link_title = db.Column(db.String(255), nullable=True)
    link_description = db.Column(db.Text, nullable=True)
    link_image = db.Column(db.String(500), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    # إن كان المنشور مكتوباً على حائط شخص آخر، يُخزّن هنا صاحب الحائط.
    # NULL يعني منشور عادي على حساب كاتبه.
    wall_owner_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id'),
        nullable=True,
        index=True,
    )
    visibility = db.Column(db.String(20), default='public', nullable=False, index=True)

    shared_video_id = db.Column(
        db.Integer,
        db.ForeignKey('videos.id'),
        nullable=True,
        index=True,
    )
    shared_video = db.relationship(
        'Video',
        foreign_keys=[shared_video_id],
        backref=db.backref('shared_posts', lazy='dynamic'),
    )

    wall_owner = db.relationship(
        'User',
        foreign_keys=[wall_owner_id],
        backref=db.backref('wall_posts', lazy='dynamic'),
    )
    comments = db.relationship('Comment', backref='post', lazy='dynamic', cascade='all, delete-orphan')
    likes = db.relationship('Like', backref='post', lazy='dynamic', cascade='all, delete-orphan')
    hashtags = db.relationship('Hashtag', secondary='post_hashtags', back_populates='posts', lazy='dynamic')

    def like_count(self):
        return self.likes.count()

    def comment_count(self):
        return self.comments.count()

    def __repr__(self):
        return f'<Post {self.id}>'
