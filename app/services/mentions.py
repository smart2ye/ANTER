"""ANTER: نظام الإشارات (@mention) — موحّد للمنشورات والتعليقات.

القواعد:
- @username: يعمل فقط إذا كنت تتابع ذلك المستخدم.
- @متابعين: إشعار جماعي لكل من يتابعك (بحد 3 مرات/يوم).
- استثناء: في الرد على تعليق، يُشار تلقائيًا لصاحب التعليق الأصلي (حتى لو لم يكن متابعًا).
- حد أقصى: 10 إشارات فردية لكل منشور/تعليق.
- إعداد الخصوصية: mention_privacy (everyone / followers_only / nobody).
"""

from __future__ import annotations
import re
from datetime import datetime, timedelta

from flask import current_app
from flask_login import current_user

from app.extensions import db
from app.models import User, Follow, Notification, UserActivity

MAX_MENTIONS_PER_POST = 10
GROUP_MENTION_DAILY_LIMIT = 3
GROUP_MENTION_KEY = 'group_mention'

# مرادفات الإشارة الجماعية
GROUP_ALIASES = {'متابعين', 'followers', 'المتابعين'}
GROUP_ALL_ALIASES = {'الجميع', 'everyone', 'all'}
SYSTEM_IDS = {2, 3, 4}  # الحسابات النظامية

# regex لكل @mention
MENTION_PATTERN = re.compile(r'@([\w\u0600-\u06FF.]+)')


def _is_group_alias(token: str) -> bool:
    return token.strip().lower() in GROUP_ALIASES


def _is_group_all(token: str) -> bool:
    return token.strip().lower() in GROUP_ALL_ALIASES


def _extract_mentions(text: str) -> list[str]:
    if not text:
        return []
    return MENTION_PATTERN.findall(text)


def _follows(follower_id: int, followed_id: int) -> bool:
    """هل follower_id يتابع followed_id؟"""
    return db.session.query(
        Follow.query.filter_by(follower_id=follower_id, followed_id=followed_id).exists()
    ).scalar()


FOUNDER_ID = 1  # حساب المؤسس


def _can_mention(actor: User, target: User) -> bool:
    """هل يستطيع actor ذكر target؟"""
    if actor.id == target.id:
        return False
    if target.is_deleted:
        return False
    if not actor.id or not target.id:
        return False

    # استثناء المؤسس: يمكنه الإشارة لأي شخص بغض النظر عن الخصوصية أو المتابعة.
    if actor.id == FOUNDER_ID:
        return True

    privacy = (target.mention_privacy or 'followers_only').lower()
    if privacy == 'nobody':
        return False
    if privacy == 'everyone':
        return True
    # followers_only: يجب أن يكون actor يتابع target
    return _follows(actor.id, target.id)


def _group_mentions_today(user_id: int) -> int:
    """عدد الإشارات الجماعية التي أرسلها المستخدم اليوم."""
    since = datetime.utcnow() - timedelta(hours=24)
    return db.session.query(UserActivity).filter(
        UserActivity.user_id == user_id,
        UserActivity.action == GROUP_MENTION_KEY,
        UserActivity.created_at >= since,
    ).count()


def _record_group_mention(user_id: int, post_id: int | None, comment_id: int | None):
    db.session.add(UserActivity(
        user_id=user_id,
        action=GROUP_MENTION_KEY,
        details=f'post={post_id},comment={comment_id}',
    ))


def _already_notified(user_id: int, actor_id: int, action: str,
                      post_id: int | None, comment_id: int | None) -> bool:
    q = Notification.query.filter_by(
        user_id=user_id,
        actor_id=actor_id,
        action=action,
    )
    if post_id is not None:
        q = q.filter(Notification.post_id == post_id)
    if comment_id is not None:
        q = q.filter(Notification.comment_id == comment_id)
    return q.first() is not None


def process_mentions(text: str, actor: User, post_id: int | None = None,
                     comment_id: int | None = None,
                     reply_to_user_id: int | None = None) -> dict:
    """يعالج كل الإشارات في نص، ويُنشئ الإشعارات المناسبة.

    يُعيد dict فيه:
        - individual: عدد الإشارات الفردية المُنشأة
        - group: True إذا أُرسلت إشارة جماعية
        - group_skipped: سبب التخطي (limit / none_followers / ...)
    """
    result = {'individual': 0, 'group': False, 'group_skipped': None, 'group_all': False, 'group_all_skipped': None}
    if not text or actor is None:
        return result

    action_individual = 'mention_comment' if comment_id else 'mention_post'
    action_group = 'mention_group_comment' if comment_id else 'mention_group_post'

    tokens = _extract_mentions(text)
    if not tokens:
        return result

    # 1) رد على تعليق → إشارة تلقائية لصاحب التعليق
    auto_target_ids: set[int] = set()
    if reply_to_user_id and reply_to_user_id != actor.id:
        auto_target_ids.add(reply_to_user_id)

    # 2) إشارات فردية + كشف الجماعية
    group_requested = False
    group_all_requested = False
    individual_targets: list[User] = []
    seen_ids: set[int] = set()

    for token in tokens:
        if _is_group_alias(token):
            group_requested = True
            continue
        if _is_group_all(token):
            # فقط المؤسس يستطيع استخدام @الجميع — نتجاهل من غيره
            if actor.id == FOUNDER_ID:
                group_all_requested = True
            continue
        user = User.query.filter_by(username=token).first()
        if not user or user.id in seen_ids or user.id == actor.id:
            continue
        if user.id in auto_target_ids:
            continue
        if not _can_mention(actor, user):
            continue
        seen_ids.add(user.id)
        individual_targets.append(user)

    # قَصّ إلى الحد الأقصى
    individual_targets = individual_targets[:MAX_MENTIONS_PER_POST]

    # 3) إنشاء إشعارات الإشارة الفردية
    for target in individual_targets:
        if _already_notified(target.id, actor.id, action_individual, post_id, comment_id):
            continue
        db.session.add(Notification(
            user_id=target.id,
            actor_id=actor.id,
            action=action_individual,
            post_id=post_id,
            comment_id=comment_id,
        ))
        result['individual'] += 1

    # 4) الإشارات التلقائية (رد على تعليق)
    for target_id in auto_target_ids:
        if _already_notified(target_id, actor.id, action_individual, post_id, comment_id):
            continue
        db.session.add(Notification(
            user_id=target_id,
            actor_id=actor.id,
            action=action_individual,
            post_id=post_id,
            comment_id=comment_id,
        ))
        result['individual'] += 1

    # 5) الإشارة الجماعية
    if group_requested:
        used = _group_mentions_today(actor.id)
        if used >= GROUP_MENTION_DAILY_LIMIT:
            result['group_skipped'] = 'limit'
        else:
            followers = (
                db.session.query(User)
                .join(Follow, Follow.follower_id == User.id)
                .filter(
                    Follow.followed_id == actor.id,
                    User.is_deleted.is_(False),
                    User.id != actor.id,
                )
                .all()
            )
            sent_any = False
            for f in followers:
                if _already_notified(f.id, actor.id, action_group, post_id, comment_id):
                    continue
                db.session.add(Notification(
                    user_id=f.id,
                    actor_id=actor.id,
                    action=action_group,
                    post_id=post_id,
                    comment_id=comment_id,
                ))
                sent_any = True
            if sent_any:
                _record_group_mention(actor.id, post_id, comment_id)
                result['group'] = True
            else:
                result['group_skipped'] = 'none_followers'

    # 6) الإشارة العامة @الجميع (المؤسس فقط، بلا حد يومي، تحترم nobody)
    if group_all_requested:
        action_all = 'mention_all_comment' if comment_id else 'mention_all_post'
        excluded_ids = {actor.id} | SYSTEM_IDS
        users_all = User.query.filter(
            User.is_deleted.is_(False),
            ~User.id.in_(excluded_ids),
            User.mention_privacy != 'nobody',
        ).all()
        sent_any = False
        for u in users_all:
            if _already_notified(u.id, actor.id, action_all, post_id, comment_id):
                continue
            db.session.add(Notification(
                user_id=u.id,
                actor_id=actor.id,
                action=action_all,
                post_id=post_id,
                comment_id=comment_id,
            ))
            sent_any = True
        if sent_any:
            result['group_all'] = True
            _record_group_mention(actor.id, post_id, comment_id)
        else:
            result['group_all_skipped'] = 'none'

    return result


def remaining_group_mentions(user_id: int) -> int:
    """كم إشارة جماعية متبقية لليوم؟"""
    used = _group_mentions_today(user_id)
    return max(0, GROUP_MENTION_DAILY_LIMIT - used)
