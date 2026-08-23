from flask import current_app

from app.extensions import db
from app.models import OwnerAdminBootstrap, User


_BOOTSTRAP_KEY = 'primary-owner-admin'


def ensure_configured_owner_is_admin():
    """Promote only the explicitly configured ANTER owner account at startup."""
    username = str(
        current_app.config.get('ANTER_OWNER_ADMIN_USERNAME', '')
    ).strip().lstrip('@')
    if not username:
        return False

    existing_bootstrap = OwnerAdminBootstrap.query.get(_BOOTSTRAP_KEY)
    if existing_bootstrap is not None:
        return False

    owner = User.query.filter_by(username=username).first()
    if owner is None or owner.is_admin:
        return False

    owner.is_admin = True
    db.session.add(OwnerAdminBootstrap(
        key=_BOOTSTRAP_KEY,
        user_id=owner.id,
        username_at_promotion=owner.username,
    ))
    db.session.commit()
    return True
