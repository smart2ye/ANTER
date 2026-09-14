from datetime import datetime, timedelta

from sqlalchemy import func

from app.extensions import db
from app.models import Follow, UserActivity, UserBlock, Video, VideoComment, VideoLike


def _activity_video_ids(user_id, actions):
    """Return video IDs the user has interacted with through recorded activities."""
    activities = (
        UserActivity.query
        .filter(
            UserActivity.user_id == user_id,
            UserActivity.action.in_(actions),
        )
        .order_by(UserActivity.created_at.desc())
        .limit(500)
        .all()
    )

    video_ids = set()

    for activity in activities:
        try:
            import json
            details = json.loads(activity.details or "{}")
            video_id = details.get("video_id")
            if video_id is not None:
                video_ids.add(int(video_id))
        except (TypeError, ValueError, KeyError):
            continue

    return video_ids


def _followed_author_ids(user_id):
    """Return accounts followed by the user."""
    rows = (
        db.session.query(Follow.followed_id)
        .filter(Follow.follower_id == user_id)
        .all()
    )
    return {row[0] for row in rows}


def _score_video(video, *, followed_ids, liked_ids, commented_ids, now):
    """Calculate an initial personalized Reels score."""
    score = 0.0

    # Strong personalization signals.
    if video.author_id in followed_ids:
        score += 35.0

    if video.id in liked_ids:
        score += 18.0

    if video.id in commented_ids:
        score += 22.0

    # Engagement signals.
    likes = video.like_count()
    comments = video.comment_count()
    views = max(video.views or 0, 0)
    shares = max(video.shares or 0, 0)

    score += min(likes * 1.5, 30.0)
    score += min(comments * 2.5, 25.0)
    score += min(shares * 3.0, 24.0)

    # Popularity, logarithmically bounded so huge view counts do not dominate.
    import math
    score += min(math.log1p(views) * 2.0, 20.0)

    # Freshness: newer Reels receive a controlled boost.
    created_at = video.created_at or now
    age_hours = max((now - created_at).total_seconds() / 3600.0, 0.0)

    if age_hours <= 24:
        score += 18.0
    elif age_hours <= 72:
        score += 12.0
    elif age_hours <= 168:
        score += 7.0
    else:
        score += max(0.0, 7.0 - ((age_hours - 168) / 168.0))

    return score


def rank_reels(user=None, *, limit=30, exclude_ids=None):
    """
    Return a ranked list of Reels.

    This is intentionally independent from the Home Feed ranking system.
    The first version uses signals already available in ANTER and does not
    require any database schema change.
    """
    exclude_ids = set(exclude_ids or [])
    now = datetime.utcnow()

    if user is None or not getattr(user, "is_authenticated", False):
        videos = (
            Video.query
            .filter(Video.is_reel.is_(True))
            .order_by(Video.created_at.desc())
            .limit(max(limit, 1) * 3)
            .all()
        )
        return videos[:limit]

    followed_ids = _followed_author_ids(user.id)

    blocked_ids = {
        row.blocked_id
        for row in UserBlock.query.filter_by(blocker_id=user.id).all()
    }
    blocked_ids.update(
        row.blocker_id
        for row in UserBlock.query.filter_by(blocked_id=user.id).all()
    )

    liked_ids = _activity_video_ids(
        user.id,
        {"video_reaction_add"},
    )

    commented_ids = _activity_video_ids(
        user.id,
        {"video_comment_create"},
    )

    query = Video.query.filter(
        Video.is_reel.is_(True),
        Video.author_id != user.id,
    )

    if blocked_ids:
        query = query.filter(~Video.author_id.in_(blocked_ids))

    if exclude_ids:
        query = query.filter(~Video.id.in_(exclude_ids))

    candidates = query.order_by(Video.created_at.desc()).limit(
        max(limit * 8, 80)
    ).all()

    scored = [
        (
            _score_video(
                video,
                followed_ids=followed_ids,
                liked_ids=liked_ids,
                commented_ids=commented_ids,
                now=now,
            ),
            video,
        )
        for video in candidates
    ]

    scored.sort(
        key=lambda item: (
            item[0],
            item[1].created_at or datetime.min,
        ),
        reverse=True,
    )

    return [video for _, video in scored[:limit]]
