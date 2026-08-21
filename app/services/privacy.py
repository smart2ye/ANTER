from app.models.follow import Follow


POST_VISIBILITIES = {'public', 'followers', 'only_me'}
PROFILE_VISIBILITIES = {'public', 'followers'}


def is_owner_or_admin(viewer, subject):
    return bool(viewer and subject and (viewer.id == subject.id or getattr(viewer, 'is_admin', False)))


def follows(viewer, subject):
    if not viewer or not subject or viewer.id == subject.id:
        return False
    return Follow.query.filter_by(follower_id=viewer.id, followed_id=subject.id).first() is not None


def can_view_profile(viewer, subject):
    if is_owner_or_admin(viewer, subject):
        return True
    return getattr(subject, 'profile_visibility', 'public') == 'public' or follows(viewer, subject)


def can_view_post(viewer, post):
    if is_owner_or_admin(viewer, post.author):
        return True
    if not can_view_profile(viewer, post.author):
        return False
    visibility = getattr(post, 'visibility', 'public') or 'public'
    if visibility == 'public':
        return True
    return visibility == 'followers' and follows(viewer, post.author)


def visible_posts(posts, viewer):
    return [post for post in posts if can_view_post(viewer, post)]
