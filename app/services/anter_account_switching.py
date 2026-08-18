"""Safe, owner-only switching between the founder account and ANTER assistant."""

from flask import current_app

from app.models import User
from app.services.anter_assistant import ensure_anter_assistant_user, is_anter_assistant


def is_switch_owner(user):
    if not user or not getattr(user, "is_authenticated", False):
        return False
    owner_username = current_app.config["ANTER_ASSISTANT_SWITCH_OWNER_USERNAME"]
    return user.username.casefold() == owner_username.casefold()


def get_managed_assistant():
    return ensure_anter_assistant_user()


def can_switch_to_assistant(user):
    return is_switch_owner(user) and not is_anter_assistant(user)


def can_switch_back(user, owner_id):
    if not owner_id or not is_anter_assistant(user):
        return False
    owner = db_get_user(owner_id)
    return owner is not None and is_switch_owner(owner)


def db_get_user(user_id):
    try:
        return User.query.get(int(user_id))
    except (TypeError, ValueError):
        return None
