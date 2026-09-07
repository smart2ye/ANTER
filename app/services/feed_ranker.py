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


def rank_post(
    *,
    created_at,
    likes=0,
    comments=0,
    reposts=0,
    similarity=0.0,
    is_following=False,
    is_own_post=False,
):
    """Return a hybrid ranking score for one feed post."""
    freshness = freshness_score(created_at)
    engagement = engagement_score(likes, comments, reposts)
    interest = interest_score(similarity)
    relationship = relationship_score(is_following, is_own_post)

    return (
        freshness * 4.0
        + engagement * 1.5
        + interest * 4.0
        + relationship * 3.0
    )
