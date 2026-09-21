from app.models.follow import Follow


POST_VISIBILITIES = {'public', 'followers', 'only_me'}
PROFILE_VISIBILITIES = {'public', 'followers'}


def is_owner_or_admin(viewer, subject):
    if not viewer or not subject:
        return False
    if not getattr(viewer, 'is_authenticated', False):
        return False
    viewer_id = getattr(viewer, 'id', None)
    subject_id = getattr(subject, 'id', None)
    if viewer_id is None or subject_id is None:
        return False
    return viewer_id == subject_id or bool(getattr(viewer, 'is_admin', False))


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


def can_post_on_wall(viewer, wall_owner):
    """هل يستطيع viewer الكتابة على حائط wall_owner؟

    تتبع قيم wall_visibility:
      public    = أي مستخدم مسجّل
      followers = المتابعون فقط
      mutual    = المتابعة المتبادلة فقط
      none      = الحائط مغلق
    """
    if not viewer or not wall_owner:
        return False
    if not getattr(viewer, 'is_authenticated', False):
        return False
    if viewer.id == wall_owner.id:
        return True
    if getattr(viewer, 'is_admin', False):
        return True

    policy = getattr(wall_owner, 'wall_visibility', 'public') or 'public'
    if policy == 'none':
        return False
    if policy == 'public':
        return True
    if policy == 'followers':
        return follows(viewer, wall_owner)
    if policy == 'mutual':
        return follows(viewer, wall_owner) and follows(wall_owner, viewer)
    return False


def visible_posts(posts, viewer):
    return [post for post in posts if can_view_post(viewer, post)]
