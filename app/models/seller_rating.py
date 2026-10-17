"""ANTER Haraj: تقييم البائع بعد إتمام البيع."""

from datetime import datetime
from app.extensions import db


class SellerRating(db.Model):
    __tablename__ = 'haraj_seller_ratings'

    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(
        db.Integer,
        db.ForeignKey('haraj_listings.id', ondelete='CASCADE'),
        nullable=False, index=True,
    )
    rater_id = db.Column(
        db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False, index=True,
    )
    seller_id = db.Column(
        db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False, index=True,
    )
    rating = db.Column(db.SmallInteger, nullable=False)
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        db.UniqueConstraint('listing_id', 'rater_id', name='unique_haraj_rating'),
        db.CheckConstraint('rating BETWEEN 1 AND 5', name='check_rating_range'),
    )

    listing = db.relationship('Listing', foreign_keys=[listing_id])
    rater = db.relationship('User', foreign_keys=[rater_id])
    seller = db.relationship('User', foreign_keys=[seller_id])

    def __repr__(self):
        return f'<SellerRating {self.rating}★ listing={self.listing_id}>'


def seller_rating_stats(seller_id):
    """يُعيد (متوسط، عدد) تقييمات بائع معين."""
    from sqlalchemy import func
    result = db.session.query(
        func.avg(SellerRating.rating),
        func.count(SellerRating.id),
    ).filter(SellerRating.seller_id == seller_id).first()
    avg = float(result[0]) if result[0] else 0.0
    return round(avg, 1), (result[1] or 0)
