"""ANTER Haraj: إعلانات البيع والشراء (أثاث وأجهزة منزلية)."""

from datetime import datetime, timedelta
from app.extensions import db
from app.utils.public_ids import generate_public_id


LISTING_CATEGORIES = {
    'furniture': 'أثاث',
    'home_appliances': 'أجهزة منزلية',
}

LISTING_TYPES = {
    'sell': 'للبيع',
    'buy': 'مطلوب',
}

LISTING_CONDITIONS = {
    'new': 'جديد',
    'used': 'مستعمل',
}

LISTING_STATUSES = {
    'active': 'نشط',
    'sold': 'مباع',
    'expired': 'منتهي',
}


def default_expires_at():
    return datetime.utcnow() + timedelta(days=30)


class Listing(db.Model):
    __tablename__ = 'haraj_listings'

    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(
        db.String(40), unique=True, nullable=False,
        default=lambda: generate_public_id('h'), index=True,
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey('users.id'), nullable=False, index=True,
    )

    category = db.Column(db.String(30), nullable=False, index=True)
    listing_type = db.Column(db.String(10), nullable=False, default='sell')
    condition = db.Column(db.String(10), nullable=False, default='used')

    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False, default='')
    price = db.Column(db.Integer, nullable=True)
    negotiable = db.Column(db.Boolean, nullable=False, default=False)

    region = db.Column(db.String(50), nullable=False, index=True)
    city = db.Column(db.String(50), nullable=False, index=True)

    status = db.Column(
        db.String(20), nullable=False, default='active',
        server_default='active', index=True,
    )

    show_whatsapp = db.Column(db.Boolean, nullable=False, default=False)
    whatsapp_number = db.Column(db.String(20), nullable=True)

    # تعهد بدفع 1% لموقع أنتر عند إتمام البيع
    pledge_accepted = db.Column(
        db.Boolean, nullable=False, default=False, server_default='false',
    )
    pledge_at = db.Column(db.DateTime, nullable=True)

    views_count = db.Column(db.Integer, nullable=False, default=0)
    reports_count = db.Column(db.Integer, nullable=False, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow,
    )
    expires_at = db.Column(
        db.DateTime, default=default_expires_at, nullable=False, index=True,
    )

    seller = db.relationship('User', foreign_keys=[user_id])
    images = db.relationship(
        'ListingImage', backref='listing', lazy='dynamic',
        cascade='all, delete-orphan',
        order_by='ListingImage.position',
    )

    def is_active(self):
        return (
            self.status == 'active'
            and self.expires_at is not None
            and self.expires_at > datetime.utcnow()
        )

    def primary_image(self):
        return self.images.filter_by(position=1).first() or self.images.first()

    def __repr__(self):
        return f'<Listing {self.public_id}>'


class ListingImage(db.Model):
    __tablename__ = 'haraj_listing_images'

    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(
        db.Integer,
        db.ForeignKey('haraj_listings.id', ondelete='CASCADE'),
        nullable=False, index=True,
    )
    image_data = db.Column(db.LargeBinary, nullable=False)
    image_mime = db.Column(db.String(100), nullable=False)
    position = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<ListingImage {self.id} pos={self.position}>'
