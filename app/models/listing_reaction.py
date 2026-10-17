"""ANTER Haraj: تفاعلات الإعلانات (إعجاب / حفظ)."""

from datetime import datetime
from app.extensions import db


class ListingReaction(db.Model):
    __tablename__ = 'haraj_listing_reactions'

    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(
        db.Integer,
        db.ForeignKey('haraj_listings.id', ondelete='CASCADE'),
        nullable=False, index=True,
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False, index=True,
    )
    # 'like' أو 'save'
    reaction_type = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        db.UniqueConstraint('listing_id', 'user_id', 'reaction_type',
                            name='unique_haraj_reaction'),
    )

    user = db.relationship('User', foreign_keys=[user_id])
    listing = db.relationship('Listing', foreign_keys=[listing_id])

    def __repr__(self):
        return f'<ListingReaction {self.reaction_type} listing={self.listing_id} user={self.user_id}>'
