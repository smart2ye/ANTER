"""ANTER: بيانات مجمّعة للمنشورات (بدل N+1 في القوالب)."""
from collections import defaultdict

from sqlalchemy import func

from app.extensions import db
from app.models import Like, Comment, User


REACTION_KEYS = ('like', 'love', 'haha', 'angry', 'sad')


def batch_post_data(post_ids, current_user_id=None, recent_limit=3):
    """يعيد {post_id: {counts, recent, user_reaction, comment_count}}.

    كل الاستعلامات دفعة واحدة بدل استدعاء دالة لكل منشور.
    """
    if not post_ids:
        return {}

    post_ids = list(set(post_ids))

    data = {}
    for pid in post_ids:
        data[pid] = {
            'counts': {k: 0 for k in REACTION_KEYS},
            'recent': [],
            'user_reaction': None,
            'comment_count': 0,
        }

    # 1. Reaction counts grouped by (post, type)
    for pid, rtype, cnt in db.session.query(
        Like.post_id, Like.reaction_type, func.count(Like.id)
    ).filter(Like.post_id.in_(post_ids)).group_by(Like.post_id, Like.reaction_type).all():
        if rtype in REACTION_KEYS:
            data[pid]['counts'][rtype] = cnt

    # 2. Current user's reactions
    if current_user_id:
        for pid, rtype in db.session.query(
            Like.post_id, Like.reaction_type
        ).filter(Like.post_id.in_(post_ids), Like.user_id == current_user_id).all():
            data[pid]['user_reaction'] = rtype

    # 3. Comment counts
    for pid, cnt in db.session.query(
        Comment.post_id, func.count(Comment.id)
    ).filter(Comment.post_id.in_(post_ids)).group_by(Comment.post_id).all():
        data[pid]['comment_count'] = cnt

    # 4. Recent reaction users (latest 3 per post, current user first)
    if current_user_id:
        rows = db.session.query(
            Like.post_id, Like.user_id
        ).filter(Like.post_id.in_(post_ids)).order_by(
            Like.post_id, Like.created_at.desc(), Like.id.desc()
        ).all()

        by_post = defaultdict(list)
        for pid, uid in rows:
            by_post[pid].append(uid)

        ordered_uids = {}
        all_uids = set()
        for pid in post_ids:
            uids = by_post.get(pid, [])
            cu = current_user_id if current_user_id in uids else None
            ordered = []
            seen = set()
            if cu:
                ordered.append(cu)
                seen.add(cu)
            for uid in uids:
                if len(ordered) >= recent_limit:
                    break
                if uid in seen:
                    continue
                ordered.append(uid)
                seen.add(uid)
            ordered_uids[pid] = ordered
            all_uids.update(ordered)

        if all_uids:
            users_map = {
                u.id: u for u in User.query.filter(
                    User.id.in_(all_uids),
                    User.is_deleted.is_(False),
                ).all()
            }
            for pid in post_ids:
                data[pid]['recent'] = [
                    {
                        'id': uid,
                        'name': users_map[uid].name or users_map[uid].username or 'مستخدم',
                        'is_current_user': uid == current_user_id,
                    }
                    for uid in ordered_uids.get(pid, [])
                    if uid in users_map
                ]

    return data
