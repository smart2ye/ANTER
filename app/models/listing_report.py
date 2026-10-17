"""ANTER Haraj: بلاغات على إعلانات الحراج."""

from datetime import datetime
from app.extensions import db


class ListingReport(db.Model):
    __tablename__ = 'haraj_listing_reports'

    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(
        db.Integer,
        db.ForeignKey('haraj_listings.id', ondelete='CASCADE'),
        nullable=False, index=True,
    )
    reporter_id = db.Column(
        db.Integer, db.ForeignKey('users.id'), nullable=False, index=True,
    )
    reason = db.Column(db.String(50), nullable=False)
    details = db.Column(db.Text, nullable=True)
    status = db.Column(
        db.String(20), nullable=False, default='pending',
        server_default='pending', index=True,
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    resolved_by = db.Column(
        db.Integer, db.ForeignKey('users.id'), nullable=True,
    )

    listing = db.relationship('Listing', foreign_keys=[listing_id])
    reporter = db.relationship('User', foreign_keys=[reporter_id])
    resolver = db.relationship('User', foreign_keys=[resolved_by])

    def __repr__(self):
        return f'<ListingReport {self.id} status={self.status}>'
