from datetime import datetime

from app.extensions import db


class OwnerAdminBootstrap(db.Model):
    """Records the one-time bootstrap promotion for the configured ANTER owner."""

    __tablename__ = 'owner_admin_bootstrap'

    key = db.Column(db.String(64), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    username_at_promotion = db.Column(db.String(80), nullable=False)
    promoted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
