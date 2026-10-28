"""ANTER: مسار التوثيق (Verification Progress).

- يحسب تقدّم المستخدم نحو العلامة الزرقاء من بيانات حقيقية.
- 7 مهام، كل مهمة مستقلة، نسبة موحّدة (كل مهمة = 1/7).
- المنح تلقائي عند 100% إن لم يكن موثّقًا ولا مقفلًا.
- يحترم verification_locked (قرار الأدمن بإزالة التوثيق).
"""
from datetime import datetime, timedelta

from sqlalchemy import func, and_, or_

from app.extensions import db
from app.models import User, Post, Follow, Story, Comment, Notification


TOTAL_TASKS = 7

# الحدود
STREAK_DAYS = 7
FOLLOWERS_TARGET = 5
POSTS_TARGET = 10
STORIES_TARGET = 5
COMMENTS_TARGET = 10

# الصور الافتراضية (لا تُعدّ صورة مخصصة)
_DEFAULT_AVATARS = {
    'img/default_avatar_male.webp',
    'img/default_avatar_female.webp',
    'img/default_avatar_male.png',
    'img/default_avatar_female.png',
    'default.png',
}


def _is_default_avatar(user: User) -> bool:
    if user.avatar_data:
        return False
    avatar = (user.avatar or '').strip()
    if not avatar:
        return True
    return avatar in _DEFAULT_AVATARS


def _count_consecutive_days(user_id: int) -> int:
    """أطول سلسلة أيام متتالية (UTC) فيها منشور واحد على الأقل.

    نأخذ منشورات آخر 14 يومًا (نافذة أوسع من الهدف لتفادي فقدان بداية السلسلة)،
    نجمع الأيام الفريدة، ثم نعدّ أطول سلسلة متتالية.
    """
    cutoff = datetime.utcnow() - timedelta(days=14)
    rows = (
        db.session.query(func.date(Post.created_at))
        .filter(
            Post.author_id == user_id,
            Post.created_at >= cutoff,
            or_(Post.moderation_status.is_(None), Post.moderation_status != 'removed'),
        )
        .distinct()
        .all()
    )
    if not rows:
        return 0

    from datetime import date as _date
    parsed = set()
    for r in rows:
        v = r[0]
        if v is None:
            continue
        if isinstance(v, _date):
            parsed.add(v)
        elif isinstance(v, str):
            try:
                parsed.add(_date.fromisoformat(v[:10]))
            except Exception:
                continue
    days = sorted(parsed)
    if not days:
        return 0

    best = 1
    current = 1
    for i in range(1, len(days)):
        if (days[i] - days[i - 1]).days == 1:
            current += 1
            if current > best:
                best = current
        else:
            current = 1
    return best


def _count_valid_followers(user_id: int) -> int:
    """متابعون غير محظورين، غير محذوفين، وليسوا المساعد الآلي."""
    rows = (
        db.session.query(Follow.follower_id)
        .join(User, User.id == Follow.follower_id)
        .filter(
            Follow.followed_id == user_id,
            User.is_deleted.is_(False),
            User.is_banned.is_(False),
            User.username != 'anter_assistant',
        )
        .distinct()
        .all()
    )
    return len(rows)


def _count_posts(user_id: int) -> int:
    return (
        db.session.query(func.count(Post.id))
        .filter(
            Post.author_id == user_id,
            or_(Post.moderation_status.is_(None), Post.moderation_status != 'removed'),
        )
        .scalar()
        or 0
    )


def _count_stories(user_id: int) -> int:
    """نحسب القصص بغض النظر عن الحذف (is_active=False عند الحذف).

    هذا يمنع التحايل بالحذف وإعادة الإنشاء، لكنه لا يعاقب من حذف قصة قديمة.
    """
    return (
        db.session.query(func.count(Story.id))
        .filter(Story.user_id == user_id)
        .scalar()
        or 0
    )


def _count_comments_on_others(user_id: int) -> int:
    """تعليقات على منشورات الآخرين فقط، غير محذوفة، على منشورات غير مزالة."""
    return (
        db.session.query(func.count(Comment.id))
        .join(Post, Post.id == Comment.post_id)
        .filter(
            Comment.author_id == user_id,
            Post.author_id != user_id,
            or_(Post.moderation_status.is_(None), Post.moderation_status != 'removed'),
        )
        .scalar()
        or 0
    )


def _is_profile_complete(user: User) -> bool:
    if not user.name or len((user.name or '').strip()) < 3:
        return False
    if not (user.bio or '').strip():
        return False
    if _is_default_avatar(user):
        return False
    if not (user.gender or '').strip():
        return False
    return True


def _is_account_safe(user: User) -> bool:
    if user.is_banned:
        return False
    if (user.warning_count or 0) > 0:
        return False
    now = datetime.utcnow()
    if user.suspended_until and user.suspended_until > now:
        return False
    if user.restricted_until and user.restricted_until > now:
        return False
    return True


def compute_progress(user: User) -> dict:
    """يعيد: percent (0-100), tasks (list), granted (bool)."""
    streak = _count_consecutive_days(user.id)
    followers = _count_valid_followers(user.id)
    posts = _count_posts(user.id)
    stories = _count_stories(user.id)
    comments = _count_comments_on_others(user.id)
    profile_ok = _is_profile_complete(user)
    safety_ok = _is_account_safe(user)

    tasks = [
        {
            'key': 'streak',
            'label': 'الاستمرارية في النشر',
            'hint': 'نشر منشور واحد يوميًا لمدة 7 أيام متتالية',
            'current': min(streak, STREAK_DAYS),
            'target': STREAK_DAYS,
            'done': streak >= STREAK_DAYS,
            'link': '/posts/create',
        },
        {
            'key': 'followers',
            'label': 'الحصول على متابعين',
            'hint': '5 متابعين حقيقيين (بلا حسابات محظورة)',
            'current': min(followers, FOLLOWERS_TARGET),
            'target': FOLLOWERS_TARGET,
            'done': followers >= FOLLOWERS_TARGET,
            'link': '/explore',
        },
        {
            'key': 'posts',
            'label': 'نشر المنشورات',
            'hint': '10 منشورات غير محذوفة',
            'current': min(posts, POSTS_TARGET),
            'target': POSTS_TARGET,
            'done': posts >= POSTS_TARGET,
            'link': '/posts/create',
        },
        {
            'key': 'stories',
            'label': 'نشر القصص',
            'hint': '5 قصص',
            'current': min(stories, STORIES_TARGET),
            'target': STORIES_TARGET,
            'done': stories >= STORIES_TARGET,
            'link': '/?open_story=1',
        },
        {
            'key': 'comments',
            'label': 'التفاعل مع المجتمع',
            'hint': '10 تعليقات على منشورات مستخدمين آخرين',
            'current': min(comments, COMMENTS_TARGET),
            'target': COMMENTS_TARGET,
            'done': comments >= COMMENTS_TARGET,
            'link': '/',
        },
        {
            'key': 'profile',
            'label': 'إكمال الحساب',
            'hint': 'الاسم + السيرة + الصورة + الجنس',
            'current': 1 if profile_ok else 0,
            'target': 1,
            'done': profile_ok,
            'link': '/users/edit',
        },
        {
            'key': 'safety',
            'label': 'سلامة الحساب',
            'hint': 'بلا حظر أو إنذارات أو تعليق نشط',
            'current': 1 if safety_ok else 0,
            'target': 1,
            'done': safety_ok,
            'link': None,
        },
    ]

    done_count = sum(1 for t in tasks if t['done'])
    percent = round(done_count * 100 / TOTAL_TASKS)

    return {
        'percent': percent,
        'tasks': tasks,
        'done_count': done_count,
        'total': TOTAL_TASKS,
    }


def grant_verification(user: User, source: str = 'progress') -> bool:
    """يمنح التوثيق إن كان مسموحًا. يعيد True إن مُنح الآن.

    يحترم:
    - verification_locked: الأدمن أقفل → لا منح تلقائي.
    - is_verified: موثّق أصلًا.
    """
    if user.verification_locked:
        return False
    if user.is_verified:
        return False
    user.is_verified = True
    user.verification_source = source
    try:
        db.session.add(Notification(
            user_id=user.id,
            actor_id=user.id,
            action='verification_approved',
            extra_text='🎉 حصلت على العلامة الزرقاء بعد إكمال متطلبات التوثيق.',
        ))
        db.session.commit()
        return True
    except Exception:
        db.session.rollback()
        return False


def maybe_grant_progress_verification(user: User) -> bool:
    """يُستدعى عند فتح صفحة التوثيق. إن 100% → منح."""
    if user.is_verified or user.verification_locked:
        return False
    progress = compute_progress(user)
    if progress['percent'] >= 100:
        return grant_verification(user, source='progress')
    return False
