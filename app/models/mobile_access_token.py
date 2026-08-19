from datetime import datetime

from app.extensions import db


class MobileAccessToken(db.Model):
    """رمز وصول قابل للإلغاء لجهاز ANTER Messenger؛ لا تُحفظ قيمة الرمز الخام."""

    __tablename__ = 'mobile_access_tokens'

    id = db.Column(db.Integer, primary_key=True)
    token_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    device_name = db.Column(db.String(120), nullable=False, default='ANTER Messenger')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    last_used_at = db.Column(db.DateTime, nullable=True)
    revoked_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship('User', backref=db.backref('mobile_access_tokens', lazy='dynamic'))

    @property
    def is_valid(self):
        return self.revoked_at is None and self.expires_at > datetime.utcnow()

