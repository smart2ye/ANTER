"""ANTER Haraj: تعليقات على الإعلانات."""

from datetime import datetime
from app.extensions import db


class ListingComment(db.Model):
    __tablename__ = 'haraj_listing_comments'

    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(
        db.Integer,
        db.ForeignKey('haraj_listings.id', ondelete='CASCADE'),
        nullable=False, index=True,
    )
    author_id = db.Column(
        db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False, index=True,
    )
    parent_id = db.Column(
        db.Integer,
        db.ForeignKey('haraj_listing_comments.id', ondelete='CASCADE'),
        nullable=True, index=True,
    )
    content = db.Column(db.Text, nullable=False)
    is_deleted = db.Column(
        db.Boolean, nullable=False, default=False, server_default='false',
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    author = db.relationship('User', foreign_keys=[author_id])
    listing = db.relationship('Listing', foreign_keys=[listing_id])
    parent = db.relationship(
        'ListingComment', remote_side=[id], foreign_keys=[parent_id],
        backref=db.backref('replies', cascade='all, delete-orphan', lazy='dynamic'),
    )

    def __repr__(self):
        return f'<ListingComment {self.id} listing={self.listing_id}>'
