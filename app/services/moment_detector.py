from datetime import datetime, timedelta

from app.extensions import db
from app.models import Post, Moment, MomentPost


DEFAULT_WINDOW_HOURS = 24
MIN_POSTS_FOR_MOMENT = 3
MAX_POSTS_PER_SCAN = 200


def _normalize_hashtag(name):
    return (name or "").strip().lower().lstrip("#")


def _post_hashtags(post):
    return {
        _normalize_hashtag(tag.name)
        for tag in post.hashtags.all()
        if _normalize_hashtag(tag.name)
    }


def find_matching_moment(post, window_hours=DEFAULT_WINDOW_HOURS):
    """العثور على Moment نشط مرتبط بهاشتاقات المنشور ضمن نافذة زمنية."""
    hashtags = _post_hashtags(post)

    if not hashtags:
        return None

    since = post.created_at - timedelta(hours=window_hours)
    until = post.created_at + timedelta(hours=window_hours)

    moments = (
        Moment.query
        .filter(
            Moment.status == "active",
            Moment.created_at <= until,
            Moment.created_at >= since,
        )
        .order_by(Moment.updated_at.desc())
        .limit(50)
        .all()
    )

    for moment in moments:
        moment_posts = (
            MomentPost.query
            .filter_by(moment_id=moment.id)
            .join(Post, MomentPost.post_id == Post.id)
            .limit(MAX_POSTS_PER_SCAN)
            .all()
        )

        for link in moment_posts:
            if hashtags.intersection(_post_hashtags(link.post)):
                return moment

    return None


def detect_for_post(post, window_hours=DEFAULT_WINDOW_HOURS):
    """
    يربط المنشور بـ Moment موجود، أو ينشئ Moment جديدًا
    عندما تتوفر إشارات كافية.
    """
    if not post or not post.created_at:
        return None

    existing = (
        MomentPost.query
        .filter_by(post_id=post.id)
        .first()
    )

    if existing:
        return existing.moment

    hashtags = _post_hashtags(post)

    if not hashtags:
        return None

    moment = find_matching_moment(post, window_hours)

    if moment:
        db.session.add(
            MomentPost(
                moment_id=moment.id,
                post_id=post.id,
            )
        )
        moment.updated_at = datetime.utcnow()
        db.session.flush()
        return moment

    # البحث عن المنشورات العامة ذات الهاشتاق المشترك
    since = post.created_at - timedelta(hours=window_hours)
    until = post.created_at + timedelta(hours=window_hours)

    candidate_posts = (
        Post.query
        .filter(
            Post.id != post.id,
            Post.visibility == "public",
            Post.created_at >= since,
            Post.created_at <= until,
        )
        .order_by(Post.created_at.desc())
        .limit(MAX_POSTS_PER_SCAN)
        .all()
    )

    related_posts = []

    for candidate in candidate_posts:
        if hashtags.intersection(_post_hashtags(candidate)):
            related_posts.append(candidate)

    if len(related_posts) + 1 < MIN_POSTS_FOR_MOMENT:
        return None

    primary_tag = next(iter(hashtags))

    moment = Moment(
        title=f"#{primary_tag}",
        description=f"منشورات متداولة حول #{primary_tag}",
        status="active",
        created_at=post.created_at,
        updated_at=datetime.utcnow(),
    )

    db.session.add(moment)
    db.session.flush()

    # إضافة المنشور الحالي + المنشورات المرتبطة
    posts_to_link = [post] + related_posts

    for related_post in posts_to_link:
        db.session.add(
            MomentPost(
                moment_id=moment.id,
                post_id=related_post.id,
            )
        )

    db.session.flush()

    return moment
