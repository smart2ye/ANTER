"""خدمة الحصاد السنوي — تجمع بيانات المستخدم لعام معيّن.

تُستخدم من قِبل year_card.py لرسم بطاقة PNG قابلة للمشاركة.
قراءة فقط — لا كتابة على قاعدة البيانات.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func

from app.extensions import db
from app.models import User, Post, Like, Comment, Follow


# ANTER: توقيت الجزيرة العربية (+03:00) — حدود السنة تُحسب بتوقيتنا.
ARABIA_OFFSET = timedelta(hours=3)


def _year_bounds_utc(year: int):
    """حدود السنة بتوقيت +03 مُحوّلة إلى UTC (كما يُخزَّن في DB)."""
    start_local = datetime(year, 1, 1)
    end_local = datetime(year + 1, 1, 1)
    return start_local - ARABIA_OFFSET, end_local - ARABIA_OFFSET


def _top_post_for_year(user_id: int, year: int):
    """أفضل منشور للسنة بعدد الإعجابات (ثم التعليقات كتعادل)."""
    start, end = _year_bounds_utc(year)

    posts = (
        Post.query
        .filter(
            Post.author_id == user_id,
            Post.created_at >= start,
            Post.created_at < end,
        )
        .all()
    )
    if not posts:
        return None, 0, 0

    best = None
    best_likes = -1
    best_comments = -1
    for p in posts:
        likes = Like.query.filter_by(post_id=p.id).count()
        comments = Comment.query.filter_by(post_id=p.id).count()
        if (likes, comments) > (best_likes, best_comments):
            best = p
            best_likes = likes
            best_comments = comments

    return best, best_likes, best_comments


def _top_interactors(user_id: int, year: int, limit: int = 5):
    """أكثر من تفاعل مع المستخدم خلال السنة (إعجابات + تعليقات على منشوراته)."""
    start, end = _year_bounds_utc(year)

    post_ids = [
        row[0] for row in
        db.session.query(Post.id).filter(
            Post.author_id == user_id,
            Post.created_at >= start,
            Post.created_at < end,
        ).all()
    ]
    if not post_ids:
        return []

    counts: dict[int, int] = {}

    for (uid,) in db.session.query(Like.user_id).filter(
        Like.post_id.in_(post_ids),
        Like.user_id != user_id,
    ).all():
        counts[uid] = counts.get(uid, 0) + 1

    for (uid,) in db.session.query(Comment.author_id).filter(
        Comment.post_id.in_(post_ids),
        Comment.author_id != user_id,
    ).all():
        counts[uid] = counts.get(uid, 0) + 1

    top = sorted(counts.items(), key=lambda x: -x[1])[:limit]
    result = []
    for uid, n in top:
        u = db.session.get(User, uid)
        if u and not getattr(u, 'is_deleted', False):
            result.append({
                'username': u.username,
                'name': u.name or u.username,
                'interactions': n,
            })
    return result


def collect(user_id: int, year: int) -> dict:
    """يجمع بيانات الحصاد السنوي كمستند JSON-قابل للتمرير."""
    user = db.session.get(User, user_id)
    if not user:
        raise ValueError('user not found')

    start, end = _year_bounds_utc(year)

    post_ids = [
        row[0] for row in
        db.session.query(Post.id).filter(
            Post.author_id == user_id,
            Post.created_at >= start,
            Post.created_at < end,
        ).all()
    ]

    likes_received = (
        Like.query.filter(Like.post_id.in_(post_ids)).count()
        if post_ids else 0
    )
    comments_received = (
        Comment.query.filter(Comment.post_id.in_(post_ids)).count()
        if post_ids else 0
    )

    followers = Follow.query.filter_by(followed_id=user_id).count()
    following = Follow.query.filter_by(follower_id=user_id).count()

    top_post, top_likes, top_comments = _top_post_for_year(user_id, year)

    return {
        'user_info': {
            'name': user.name or user.username,
            'username': user.username,
            'joined_date': user.created_at.strftime('%Y-%m-%d') if user.created_at else None,
            'is_verified': bool(getattr(user, 'is_verified', False)),
        },
        'year': year,
        'stats': {
            'total_posts': len(post_ids),
            'likes_received': likes_received,
            'comments_received': comments_received,
            'total_interactions': likes_received + comments_received,
            'followers': followers,
            'following': following,
        },
        'top_post': {
            'id': top_post.id,
            'content': (top_post.content or '')[:400],
            'likes': top_likes,
            'comments': top_comments,
            'has_image': bool(top_post.image_data or top_post.image),
        } if top_post else None,
        'top_interactors': _top_interactors(user_id, year, limit=5),
    }
