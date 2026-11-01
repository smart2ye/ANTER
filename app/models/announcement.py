from app.extensions import db
from datetime import datetime


class Announcement(db.Model):
    """ANTER: إعلانات الشريط المتحرك — متعددة، قابلة للترتيب والتفعيل."""
    __tablename__ = 'announcements'

    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False, default='')
    sort_order = db.Column(db.Integer, nullable=False, default=0, server_default='0', index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default='true')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Announcement {self.id}>'
