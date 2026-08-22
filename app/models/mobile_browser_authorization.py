from datetime import datetime

from app.extensions import db


class MobileBrowserAuthorization(db.Model):
    """رمز قصير العمر وأحادي الاستخدام يربط جلسة موقع ANTER بتطبيق Messenger."""

    __tablename__ = 'mobile_browser_authorizations'

    id = db.Column(db.Integer, primary_key=True)
    code_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    state = db.Column(db.String(120), nullable=False)
    redirect_uri = db.Column(db.String(255), nullable=False)
    device_name = db.Column(db.String(120), nullable=False, default='ANTER Messenger')
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    consumed_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship('User', backref=db.backref('mobile_browser_authorizations', lazy='dynamic'))

    @property
    def is_valid(self):
        return self.consumed_at is None and self.expires_at > datetime.utcnow()
