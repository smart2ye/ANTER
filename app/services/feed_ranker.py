"""Ranking helpers for the ANTER home feed."""

import math
from datetime import datetime


def freshness_score(created_at, half_life_hours=36):
    """Score freshness with exponential time decay."""
    if not created_at:
        return 0.0

    age_hours = max(
        0.0,
        (datetime.utcnow() - created_at).total_seconds() / 3600,
    )
    return math.exp(-age_hours / half_life_hours)


def engagement_score(likes=0, comments=0, reposts=0):
    """Bounded engagement score so viral posts do not dominate everything."""
    raw = (likes * 1.0) + (comments * 3.0) + (reposts * 5.0)
    return math.log1p(max(0, raw))


def interest_score(similarity):
    """Convert the existing content similarity into a bounded score."""
    return max(0.0, min(1.0, similarity or 0.0))


def relationship_score(is_following=False, is_own_post=False):
    """Prioritize people the user already has a relationship with."""
    if is_own_post:
        return 1.0
    if is_following:
        return 0.75
    return 0.0


def geo_score(country_score_value=0.0):
    """ANTER: نقاط الموقع الجغرافي (0-30 → مقياس 0-3).

    لا يعتمد على GPS، بل على country_code المُدخَل عند التسجيل.
    - نفس الدولة → 30 نقطة أصلية → 3.0
    - دولة مجاورة → 15 → 1.5
    - دولة عربية → 8 → 0.8
    """
    return max(0.0, min(30.0, country_score_value or 0.0)) / 10.0


def rank_post(
    *,
    created_at,
    likes=0,
    comments=0,
    reposts=0,
    similarity=0.0,
    is_following=False,
    is_own_post=False,
    country_score=0.0,
):
    """Return a hybrid ranking score for one feed post.

    ANTER: country_score مُعامل جديد (0-30 → 0-3) لتعزيز المنشورات المحلية.
    """
    freshness = freshness_score(created_at)
    engagement = engagement_score(likes, comments, reposts)
    interest = interest_score(similarity)
    relationship = relationship_score(is_following, is_own_post)
    geo = geo_score(country_score)

    # ANTER: بوابة عمرية صريحة — أي منشور أقدم من 10 أيام لا يظهر في الـ feed.
    # half_life=36h → freshness=0.005 يعادل ~8 أيام. نستخدم 0.01 (~5.5 يوم) للحد.
    if freshness < 0.01:
        return 0.0

    # ANTER: تلاشٍ زمني للتفاعل والعلاقة — منشور قديم بتفاعل عالٍ لا يهزم الجديد.
    # relationship (خاصة is_own_post) تتلاشى بدل أن تكون 3.0 ثابتة.
    return (
        freshness * 4.0
        + engagement * 2.5 * freshness
        + interest * 4.0
        + relationship * 3.0 * (0.2 + 0.8 * freshness)
        + geo * 0.5
    )
