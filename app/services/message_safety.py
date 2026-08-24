"""قواعد خادمية مشتركة لسلامة المحادثات الخاصة."""

from sqlalchemy import or_

from app.extensions import db
from app.models import CallSignal, Follow, TypingState, UserBlock


def is_blocked_between(first_user_id, second_user_id):
    """يعيد True إذا حظر أحد الطرفين الآخر، فلا يمر أي تواصل خاص."""
    if not first_user_id or not second_user_id or first_user_id == second_user_id:
        return False
    return db.session.query(UserBlock.id).filter(
        or_(
            (UserBlock.blocker_id == first_user_id) & (UserBlock.blocked_id == second_user_id),
            (UserBlock.blocker_id == second_user_id) & (UserBlock.blocked_id == first_user_id),
        )
    ).first() is not None


def blocked_counterparty_ids(user_id):
    """معرفات الحسابات التي يوجد بينها وبين المستخدم حظر في أي اتجاه."""
    if not user_id:
        return set()
    rows = UserBlock.query.filter(
        or_(UserBlock.blocker_id == user_id, UserBlock.blocked_id == user_id)
    ).all()
    return {
        row.blocked_id if row.blocker_id == user_id else row.blocker_id
        for row in rows
    }


def block_user(blocker, blocked):
    """تسجيل الحظر وتنظيف العلاقات الزمنية التي قد تسمح بتواصل فوري قديم."""
    if blocker.id == blocked.id:
        raise ValueError('لا يمكنك حظر حسابك نفسه.')

    existing = UserBlock.query.filter_by(
        blocker_id=blocker.id,
        blocked_id=blocked.id,
    ).first()
    if existing is not None:
        return False

    db.session.add(UserBlock(blocker_id=blocker.id, blocked_id=blocked.id))
    Follow.query.filter(
        or_(
            (Follow.follower_id == blocker.id) & (Follow.followed_id == blocked.id),
            (Follow.follower_id == blocked.id) & (Follow.followed_id == blocker.id),
        )
    ).delete(synchronize_session=False)
    TypingState.query.filter(
        or_(
            (TypingState.sender_id == blocker.id) & (TypingState.receiver_id == blocked.id),
            (TypingState.sender_id == blocked.id) & (TypingState.receiver_id == blocker.id),
        )
    ).delete(synchronize_session=False)
    CallSignal.query.filter(
        or_(
            (CallSignal.sender_id == blocker.id) & (CallSignal.receiver_id == blocked.id),
            (CallSignal.sender_id == blocked.id) & (CallSignal.receiver_id == blocker.id),
        ),
        CallSignal.delivered_at.is_(None),
    ).delete(synchronize_session=False)
    return True


def unblock_user(blocker, blocked):
    """إلغاء حظر أنشأه المستخدم الحالي فقط؛ لا يمكنه إلغاء حظر الطرف الآخر."""
    row = UserBlock.query.filter_by(
        blocker_id=blocker.id,
        blocked_id=blocked.id,
    ).first()
    if row is None:
        return False
    db.session.delete(row)
    return True
