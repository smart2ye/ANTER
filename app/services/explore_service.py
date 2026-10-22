"""Explore service — بحث وترتيب موحّد لكل أنواع المحتوى.

ANTER: يجمع منطق الترتيب من:
- trends.calculate_hot_score (نفس المعادلة مُكرّرة هنا لتفادي circular import)
- hot_score مخصص للريلز
- geo_ranker (لتقوية المحتوى المحلي)
"""

import math
from datetime import datetime, timedelta
from sqlalchemy import func, or_

from app.extensions import db
from app.models import Post, Video, User, Follow, Repost
from app.services.geo_ranker import geo_score_for_post, geo_score_for_user


# ============================================================
# محرّكات الترتيب (hot score)
# ============================================================
def _hot_score(engagement, created_at):
    """Score = Engagement / (Time + 2)^1.5 — نفس منطق trends."""
    time_diff = (datetime.utcnow() - created_at).total_seconds() / 3600
    return engagement / math.pow((time_diff + 2), 1.5)


def _post_engagement(post):
    """engagement مرجّح: like=1, comment=3, repost=5."""
    likes = post.likes.count()
    comments = post.comments.count()
    try:
        reposts = Repost.query.filter_by(post_id=post.id).count()
    except Exception:
        reposts = 0
    return likes * 1 + comments * 3 + reposts * 5


def _reel_engagement(video):
    """engagement مرجّح للريل: view=0.1, like=2, comment=3, share=5."""
    likes = video.like_count()
    comments = video.comment_count()
    views = video.views or 0
    shares = video.shares or 0
    return (views * 0.1) + (likes * 2) + (comments * 3) + (shares * 5)


# ============================================================
# المنشورات
# ============================================================
def trending_posts(viewer, limit=20, query=None, hours=48):
    """منشورات رائجة — آخر N ساعة، العامة فقط."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    q = Post.query.filter(
        Post.created_at > cutoff,
        Post.visibility == 'public',
    )

    if query:
        pattern = f'%{query}%'
        q = q.filter(Post.content.ilike(pattern))

    posts = q.limit(200).all()
    scored = []
    for post in posts:
        hot = _hot_score(_post_engagement(post), post.created_at)
        geo = geo_score_for_post(post, viewer)
        # geo بأثر خفيف (0-0.3)، لا يُطغى على hot
        scored.append((post, hot + geo * 0.01))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [p for p, _ in scored[:limit]]


# ============================================================
# الريلز
# ============================================================
def trending_reels(viewer, limit=20, query=None, days=7):
    """ريلز رائجة — آخر N يوم، مع دعم البحث."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    q = Video.query.filter(
        Video.is_reel.is_(True),
        Video.created_at > cutoff,
    )

    if query:
        pattern = f'%{query}%'
        q = q.filter(or_(
            Video.title.ilike(pattern),
            Video.description.ilike(pattern),
        ))

    reels = q.limit(200).all()
    scored = []
    for v in reels:
        hot = _hot_score(_reel_engagement(v), v.created_at)
        geo = geo_score_for_post(v, viewer)
        scored.append((v, hot + geo * 0.01))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [v for v, _ in scored[:limit]]


# ============================================================
# المستخدمون (اقتراحات)
# ============================================================
def trending_users(viewer, limit=20):
    """أشخاص قد تعرفهم: أصدقاء مشتركون (×5) + نقاط جغرافية."""
    following_ids = [f.followed_id for f in viewer.following] + [viewer.id]

    second_degree = db.session.query(
        Follow.followed_id,
        func.count(Follow.follower_id).label('mutual_count')
    ).filter(
        Follow.follower_id.in_(following_ids),
        ~Follow.followed_id.in_(following_ids)
    ).group_by(Follow.followed_id).order_by(
        func.count(Follow.follower_id).desc()
    ).limit(30).all()

    suggested_ids = [row[0] for row in second_degree]
    mutual_counts = {row[0]: row[1] for row in second_degree}

    if not suggested_ids:
        recent_cutoff = datetime.utcnow() - timedelta(days=30)
        active_users = db.session.query(
            Post.author_id,
            func.count(Post.id).label('posts_count')
        ).filter(
            Post.created_at > recent_cutoff,
            ~Post.author_id.in_(following_ids)
        ).group_by(Post.author_id).order_by(
            func.count(Post.id).desc()
        ).limit(30).all()
        suggested_ids = [row[0] for row in active_users]
        mutual_counts = {row[0]: 0 for row in active_users}

    # ANTER fallback 3: المستخدمون الموثقون/المبكرون غير المتابَعين
    if not suggested_ids:
        priority_users = User.query.filter(
            ~User.id.in_(following_ids),
            User.is_deleted.is_(False),
            or_(User.is_verified.is_(True), User.is_early_member.is_(True)),
        ).order_by(User.id.desc()).limit(30).all()
        suggested_ids = [u.id for u in priority_users]
        mutual_counts = {u.id: 0 for u in priority_users}

    # ANTER fallback 4: أي مستخدم غير محذوف وغير متابَع (الأحدث أولاً)
    if not suggested_ids:
        recent_users = User.query.filter(
            ~User.id.in_(following_ids),
            User.is_deleted.is_(False),
        ).order_by(User.id.desc()).limit(30).all()
        suggested_ids = [u.id for u in recent_users]
        mutual_counts = {u.id: 0 for u in recent_users}

    users_by_id = {
        u.id: u for u in User.query.filter(
            User.id.in_(suggested_ids),
            User.is_deleted.is_(False),
        ).all()
    }

    # ANTER: عدّاد المتابعين دفعة واحدة (استعلام واحد بدل 30).
    follower_rows = db.session.query(
        Follow.followed_id,
        func.count(Follow.id),
    ).filter(Follow.followed_id.in_(suggested_ids)) \
     .group_by(Follow.followed_id).all()
    follower_counts = {uid: cnt for uid, cnt in follower_rows}

    def _score(uid):
        # ترتيب طبقـي: موثق ← مبكر ← عدد المتابعين ← (تعادل: أصدقاء أصدقاء ← geo)
        u = users_by_id.get(uid)
        if not u:
            return (-1, -1, -1, -1, -1)
        verified = 1 if getattr(u, 'is_verified', False) else 0
        early = 1 if getattr(u, 'is_early_member', False) else 0
        followers = follower_counts.get(uid, 0) or 0
        mutual = mutual_counts.get(uid, 0) or 0
        geo = geo_score_for_user(u, viewer)
        return (verified, early, followers + mutual * 2, mutual, geo)

    ranked_ids = sorted(
        [uid for uid in suggested_ids if uid in users_by_id],
        key=_score,
        reverse=True,
    )

    return [users_by_id[uid] for uid in ranked_ids[:limit]]


def normalize_arabic(text):
    """توحيد الهمزات والتشكيل والمدّ في النص العربي للبحث."""
    if not text:
        return ''
    s = str(text)
    # الهمزات
    s = s.replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا')
    s = s.replace('ٱ', 'ا')
    s = s.replace('ى', 'ي').replace('ئ', 'ي').replace('ؤ', 'و')
    # التاء المربوطة
    s = s.replace('ة', 'ه')
    # التشكيل
    for mark in ['\u064B', '\u064C', '\u064D', '\u064E', '\u064F', '\u0650', '\u0651', '\u0652', '\u0670']:
        s = s.replace(mark, '')
    # تطبيع المسافات
    s = ' '.join(s.split())
    return s.lower().strip()


def search_users(viewer, query, limit=20):
    """بحث في المستخدمين بالاسم أو اليوزر + ترتيب جغرافي."""
    if not query:
        return []
    normalized = normalize_arabic(query)
    if not normalized:
        return []

    # نجلب كل المستخدمين الآخرين ثم نُصفّي في Python (يدعم العربية بشكل صحيح)
    # مع 17 مستخدم على Aiven، هذا فعّال. لو كبر المشروع نُضيف عمود search_text مُطبّع.
    all_users = User.query.filter(
        User.id != viewer.id,
        User.is_deleted.is_(False),
    ).limit(500).all()

    matched = []
    for u in all_users:
        name_n = normalize_arabic(u.name or '')
        username_n = normalize_arabic(u.username or '')
        bio_n = normalize_arabic(u.bio or '')
        if (normalized in name_n
                or normalized in username_n
                or normalized in bio_n):
            matched.append(u)

    return sorted(matched, key=lambda u: -geo_score_for_user(u, viewer))[:limit]
