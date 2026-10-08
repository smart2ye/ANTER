from flask import Blueprint, abort, flash, render_template, request, jsonify, redirect, session, url_for
from flask import current_app, jsonify
from flask_login import login_required, current_user
from app.models import Post, Video, Like, Comment, Follow, HiddenPost, Report, User, Repost
from app.extensions import db
from app.forms.support import SupportRequestForm
from sqlalchemy import func, or_, and_
from sqlalchemy.orm import joinedload
from datetime import datetime, timedelta
from app.services.privacy import visible_posts
from app.services.feed_ranker import rank_post
from app.services.geo_ranker import geo_score_for_post
import math
import re
from collections import Counter
import os

main_bp = Blueprint('main', __name__)


@main_bp.route('/admin')
def admin_entry():
    """Redirect a signed-in administrator to the current random admin route."""
    if not current_user.is_authenticated or not current_user.is_admin:
        abort(404)
    return redirect(url_for('admin.dashboard'))


@main_bp.route('/api/messenger/release')
def messenger_release():
    """معلومة إصدار عامة يقرأها Messenger للتحقق من وجود تحديث موثوق."""
    return jsonify({
        'version': current_app.config['ANTER_MESSENGER_VERSION'],
        'downloadUrl': current_app.config['ANTER_MESSENGER_APK_URL'],
        'sha256': current_app.config['ANTER_MESSENGER_APK_SHA256'],
        'notes': current_app.config['ANTER_MESSENGER_RELEASE_NOTES'],
    })

STOP_WORDS = {'ال', 'و', 'في', 'من', 'على', 'إلى', 'عن', 'مع', 'بين', 'كل', 'بعض', 'هذا', 'هذه', 'ذلك', 'تلك', 'كان', 'كانت', 'يكون', 'تصبح', 'أصبح', 'يصبح', 'ما', 'لا', 'هل', 'أم', 'أو', 'ثم', 'حتى', 'لكن', 'لأن', 'حيث', 'بينما', 'عندما', 'إذا', 'إن', 'أن', 'قد', 'سوف', 'سيكون', 'لم', 'لن', 'ليس', 'ليست'}

def extract_keywords(text):
    if not text:
        return []
    text = re.sub(r'[^\w\s]', ' ', text)
    words = text.split()
    keywords = [w for w in words if len(w) > 2 and w not in STOP_WORDS]
    return keywords

def get_user_interests(user_id):
    interests = []
    try:
        liked_posts = db.session.query(Post.content).join(Like, Like.post_id == Post.id)\
            .filter(Like.user_id == user_id).limit(30).all()
        for post in liked_posts:
            interests.extend(extract_keywords(post.content))
        comments = Comment.query.filter_by(author_id=user_id).limit(30).all()
        for comment in comments:
            interests.extend(extract_keywords(comment.content))
        own_posts = Post.query.filter_by(author_id=user_id).limit(20).all()
        for post in own_posts:
            interests.extend(extract_keywords(post.content))
    except Exception:
        return []
    if interests:
        counter = Counter(interests)
        return [word for word, count in counter.most_common(20)]
    return []

def calculate_similarity(text, interests):
    if not interests:
        return 0
    keywords = extract_keywords(text)
    if not keywords:
        return 0
    matches = sum(1 for k in keywords if k in interests)
    return matches / len(interests) if interests else 0

def get_post_engagement_counts(post_ids):
    """Fetch like/comment/repost counts for multiple posts in batched queries."""
    if not post_ids:
        return {}

    counts = {
        post_id: {'likes': 0, 'comments': 0, 'reposts': 0}
        for post_id in post_ids
    }

    for post_id, count in db.session.query(
        Like.post_id, func.count(Like.id)
    ).filter(
        Like.post_id.in_(post_ids)
    ).group_by(Like.post_id).all():
        counts[post_id]['likes'] = count

    for post_id, count in db.session.query(
        Comment.post_id, func.count(Comment.id)
    ).filter(
        Comment.post_id.in_(post_ids)
    ).group_by(Comment.post_id).all():
        counts[post_id]['comments'] = count

    for post_id, count in db.session.query(
        Repost.post_id, func.count(Repost.id)
    ).filter(
        Repost.post_id.in_(post_ids)
    ).group_by(Repost.post_id).all():
        counts[post_id]['reposts'] = count

    return counts


def build_feed(user):
    """Build a bounded, ranked feed for both the HTML page and infinite-scroll API."""
    page_size = current_app.config['FEED_PAGE_SIZE']
    candidate_limit = current_app.config['FEED_CANDIDATE_LIMIT']
    following_ids = [follow.followed_id for follow in user.following] + [user.id]
    interests = get_user_interests(user.id)
    post_query = Post.query.options(joinedload(Post.author))

    followed_posts = post_query.filter(Post.author_id.in_(following_ids)) \
        .order_by(Post.id.desc()).limit(candidate_limit).all()
    suggested_posts = post_query.filter(
        ~Post.author_id.in_(following_ids),
        Post.created_at > datetime.utcnow() - timedelta(days=7)
    ).order_by(Post.id.desc()).limit(candidate_limit).all()

    suggested_counts = get_post_engagement_counts(
        [post.id for post in suggested_posts]
    )

    suggested_with_scores = []
    for post in suggested_posts:
        similarity = calculate_similarity(post.content, interests)
        engagement = suggested_counts.get(post.id, {})

        score = rank_post(
            created_at=post.created_at,
            likes=engagement.get('likes', 0),
            comments=engagement.get('comments', 0),
            reposts=engagement.get('reposts', 0),
            similarity=similarity,
            is_following=False,
            is_own_post=False,
            country_score=geo_score_for_post(post, user),
        )

        suggested_with_scores.append((post, score))

    suggested_with_scores.sort(key=lambda item: item[1], reverse=True)
    top_suggested = [post for post, _score in suggested_with_scores[:page_size]]

    all_posts = followed_posts + top_suggested
    if not all_posts:
        all_posts = post_query.order_by(Post.created_at.desc()).limit(candidate_limit).all()

    all_posts = visible_posts(all_posts, user)
    top_suggested = visible_posts(top_suggested, user)

    hidden_ids = {
        post_id for post_id, in db.session.query(HiddenPost.post_id)
        .filter_by(user_id=user.id).all()
    }
    if hidden_ids:
        all_posts = [post for post in all_posts if post.id not in hidden_ids]

    following_set = set(following_ids)
    engagement_counts = get_post_engagement_counts(
        [post.id for post in all_posts]
    )

    def feed_score(post):
        similarity = calculate_similarity(post.content, interests)
        is_own_post = post.author_id == user.id
        is_following = post.author_id in following_set and not is_own_post
        engagement = engagement_counts.get(post.id, {})

        return rank_post(
            created_at=post.created_at,
            likes=engagement.get('likes', 0),
            comments=engagement.get('comments', 0),
            reposts=engagement.get('reposts', 0),
            similarity=similarity,
            is_following=is_following,
            is_own_post=is_own_post,
            country_score=geo_score_for_post(post, user),
        )

    all_posts.sort(key=feed_score, reverse=True)
    return all_posts, top_suggested

@main_bp.route('/')
def index():
    # الزائر غير المسجّل → صفحة هبوط تسويقية عامة (لعرض ANTER لمحركات البحث والزوار).
    if not current_user.is_authenticated:
        return render_template('landing.html')

    all_posts, top_suggested = build_feed(current_user)
    page_size = current_app.config['FEED_PAGE_SIZE']

    # ANTER: pin مؤقت — المنشور المذكور في ?new=<id> يظهر في الأعلى مرة واحدة.
    # عند إعادة التحميل بدون query param، يعود الترتيب الطبيعي.
    pinned_post_id = request.args.get('new', type=int)
    if pinned_post_id:
        pinned = next((p for p in all_posts if p.id == pinned_post_id), None)
        if pinned:
            all_posts = [pinned] + [p for p in all_posts if p.id != pinned_post_id]

    # ANTER: كتلة ريلز مقترحة داخل الـFeed (مرة واحدة فقط).
    # نستخدم نفس خوارزمية reels_ranker ولا نلمس feed_ranker.
    feed_reels = []
    try:
        from app.services.reels_ranker import rank_reels
        feed_reels = rank_reels(current_user, limit=4)
    except Exception:
        feed_reels = []

    # ANTER: قائمة الأصدقاء لنافذة مشاركة المنشور (نفس منطق videos.reels).
    share_users = []
    try:
        from app.models import Follow, UserBlock, User as _User
        blocked_ids = {
            row.blocked_id
            for row in UserBlock.query.filter_by(blocker_id=current_user.id).all()
        }
        blocked_ids.update(
            row.blocker_id
            for row in UserBlock.query.filter_by(blocked_id=current_user.id).all()
        )
        followed_ids = {
            row.followed_id
            for row in Follow.query.filter_by(follower_id=current_user.id).all()
            if row.followed_id != current_user.id
            and row.followed_id not in blocked_ids
        }
        if followed_ids:
            share_users = (
                _User.query
                .filter(
                    _User.id.in_(followed_ids),
                    _User.is_deleted.is_(False),
                )
                .order_by(_User.name.asc(), _User.username.asc())
                .all()
            )
    except Exception:
        share_users = []

    # ANTER: كتلة ترحيب للمستخدم الجديد — تُعرض مرة واحدة عبر ?welcome=1.
    onboarding_users = []
    if request.args.get('welcome') == '1':
        try:
            from app.services.explore_service import trending_users
            onboarding_users = trending_users(current_user, limit=5)
        except Exception:
            onboarding_users = []

    return render_template(
        'index.html',
        posts=all_posts[:page_size],
        suggested_posts=top_suggested,
        feed_reels=feed_reels,
        share_users=share_users,
        onboarding_users=onboarding_users,
    )

@main_bp.route('/login')
def login_alias():
    return redirect(url_for('auth.login'))


@main_bp.route('/register')
def register_alias():
    return redirect(url_for('auth.register'))


@main_bp.route('/profile')
@login_required
def profile_alias():
    return redirect(url_for('users.profile', username=current_user.username))


@main_bp.route('/settings')
@login_required
def settings_alias():
    return redirect(url_for('users.settings'))


@main_bp.route('/api/posts')
@login_required
def api_posts():
    page = max(1, request.args.get('page', 1, type=int))
    per_page = current_app.config['FEED_PAGE_SIZE']
    all_posts, top_suggested = build_feed(current_user)
    start = (page - 1) * per_page
    end = start + per_page
    paginated_posts = all_posts[start:end]
    has_next = len(all_posts) > end
    post_counts = get_post_engagement_counts(
        [post.id for post in paginated_posts]
    )

    data = []
    for post in paginated_posts:
        engagement = post_counts.get(post.id, {})
        data.append({
            'id': post.public_id,
            'url': url_for('posts.view_post', public_id=post.public_id),
            'content': post.content,
            'image': post.image,
            'link_preview': {
                'url': post.link_url,
                'title': post.link_title,
                'description': post.link_description,
                'image': post.link_image,
            } if post.link_url else None,
            'created_at': post.created_at.strftime('%Y-%m-%d %H:%M'),
            'author': {
                'id': post.author.id,
                'name': post.author.name,
                'username': post.author.username,
                'avatar': post.author.avatar
            },
            'like_count': engagement.get('likes', 0),
            'comment_count': engagement.get('comments', 0),
            'is_author': post.author_id == current_user.id,
            'is_suggested': post in top_suggested,
            'html': render_template('_post_card.html', post=post)
        })
    return jsonify({'posts': data, 'has_next': has_next})

@main_bp.route('/privacy')
def privacy():
    return render_template('privacy.html')

@main_bp.route('/terms')
def terms():
    return render_template('terms.html')


@main_bp.route('/help', methods=['GET', 'POST'])
def help_center():
    form = SupportRequestForm()
    if form.validate_on_submit():
        last_submission = session.get('support_request_submitted_at', 0)
        now_timestamp = int(datetime.utcnow().timestamp())
        if now_timestamp - last_submission < 300:
            flash('تم استلام طلبك مؤخراً. انتظر بضع دقائق قبل إرسال طلب جديد.', 'warning')
            return redirect(url_for('main.help_center'))

        reporter = current_user if current_user.is_authenticated else User.query.filter_by(
            username=current_app.config['ANTER_ASSISTANT_USERNAME']
        ).first()
        if reporter is None:
            abort(503)

        contact = (form.contact.data or '').strip()
        report = Report(
            reporter_id=reporter.id,
            reason=f'support:{form.topic.data}',
            details=(
                '[طلب مساعدة]\n'
                f'المرسل: {current_user.name if current_user.is_authenticated else "زائر"}\n'
                f'وسيلة التواصل: {contact or "غير مقدمة"}\n\n'
                f'{form.message.data.strip()}'
            ),
        )
        db.session.add(report)
        db.session.commit()
        session['support_request_submitted_at'] = now_timestamp
        flash('تم استلام طلب المساعدة. سنراجعه ونرد عبر وسيلة التواصل التي تركتها إن وُجدت.', 'success')
        return redirect(url_for('main.help_center'))
    return render_template('help.html', form=form)


@main_bp.route('/about')
def about():
    return render_template(
        'about.html',
        anter_apk_url=current_app.config['ANTER_APK_URL'],
        anter_apk_version=current_app.config['ANTER_APK_VERSION'],
        anter_apk_size=current_app.config['ANTER_APK_SIZE'],
        anter_apk_date=current_app.config['ANTER_APK_DATE'],
    )

@main_bp.route('/offline.html')
def offline():
    return current_app.send_static_file('offline.html')

@main_bp.route('/robots.txt')
def robots_txt():
    """خدمة robots.txt من الجذر للسماح لمحركات البحث بالوصول الصحيح."""
    from flask import send_from_directory
    return send_from_directory(
        current_app.static_folder,
        'robots.txt',
        mimetype='text/plain',
    )


@main_bp.route('/d5a1393ec6a04f07aaacd9561975b833.txt')
def indexnow_key():
    """ملف التحقق من IndexNow (Bing + Yandex + Seznam + Naver)."""
    from flask import Response
    return Response('d5a1393ec6a04f07aaacd9561975b833', mimetype='text/plain')


@main_bp.route('/sitemap.xml')
def sitemap():
    """توليد خريطة الموقع (Sitemap) بشكل ديناميكي لضمان أرشفة كافة المنشورات والريلز والمستخدمين."""
    from app.models import User, Post, Video
    
    # الصفحات الثابتة الأساسية
    pages = [
        {'loc': url_for('main.about', _external=True), 'priority': 0.8, 'changefreq': 'monthly'},
        {'loc': url_for('main.help_center', _external=True), 'priority': 0.7, 'changefreq': 'monthly'},
        {'loc': url_for('main.privacy', _external=True), 'priority': 0.5, 'changefreq': 'monthly'},
        {'loc': url_for('main.terms', _external=True), 'priority': 0.5, 'changefreq': 'monthly'},
        {'loc': url_for('explore.explore', _external=True), 'priority': 0.9, 'changefreq': 'always'},
        {'loc': url_for('videos.reels', _external=True), 'priority': 0.8, 'changefreq': 'always'},
    ]
    
    # أرشفة المستخدمين (أحدث 200 مستخدم)
    users = (
        User.query
        .filter(
            User.profile_visibility == 'public',
            User.is_deleted.is_(False),
        )
        .order_by(User.created_at.desc())
        .limit(200)
        .all()
    )
    for user in users:
        pages.append({
            'loc': url_for('users.profile', username=user.username, _external=True),
            'priority': 0.7,
            'lastmod': (user.created_at or datetime.now()).strftime('%Y-%m-%d'),
            'changefreq': 'weekly'
        })
    
    # أرشفة المنشورات (أحدث 1000 منشور)
    posts = (
        Post.query
        .filter(Post.visibility == 'public')
        .order_by(Post.created_at.desc())
        .limit(1000)
        .all()
    )
    for post in posts:
        pages.append({
            'loc': url_for('posts.view_post', public_id=post.public_id, _external=True),
            'priority': 0.9,
            'lastmod': (post.updated_at or post.created_at or datetime.now()).strftime('%Y-%m-%d'),
            'changefreq': 'never'
        })
        
    # أرشفة الريلز (أحدث 500 فيديو)
    videos = Video.query.filter_by(is_reel=True).order_by(Video.created_at.desc()).limit(500).all()
    for video in videos:
        pages.append({
            'loc': url_for('videos.watch', public_id=video.public_id, _external=True),
            'priority': 0.9,
            'lastmod': (video.created_at or datetime.now()).strftime('%Y-%m-%d'),
            'changefreq': 'never'
        })

    # أرشفة الهاشتاقات النشطة (التي لديها منشوران أو أكثر)
    # نستبعد الهاشتاقات الفارغة لأنها محتوى ضعيف لا يفيد الفهرسة.
    try:
        from app.models import Hashtag
        from sqlalchemy import func as _func
        active_hashtags = (
            Hashtag.query
            .join(Hashtag.posts)
            .group_by(Hashtag.id)
            .having(_func.count(Post.id) >= 2)
            .order_by(Hashtag.name.asc())
            .limit(500)
            .all()
        )
        for tag in active_hashtags:
            pages.append({
                'loc': url_for('explore.hashtag', tag=tag.name, _external=True),
                'priority': 0.6,
                'changefreq': 'weekly'
            })
    except Exception:
        # لا نُفشل الـ sitemap إن حدث خطأ في الهاشتاقات.
        current_app.logger.exception('sitemap: hashtags failed (non-fatal)')
        
    # فرض https على كل الروابط (2026-09-27) — يمنع duplicate content
    def _force_https(u):
        if u.startswith('http://'):
            return 'https://' + u[7:]
        return u

    # بناء ملف XML
    sitemap_xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    sitemap_xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    
    for page in pages:
        sitemap_xml += '  <url>\n'
        sitemap_xml += f'    <loc>{_force_https(page["loc"])}</loc>\n'
        if 'lastmod' in page:
            sitemap_xml += f'    <lastmod>{page["lastmod"]}</lastmod>\n'
        if 'changefreq' in page:
            sitemap_xml += f'    <changefreq>{page["changefreq"]}</changefreq>\n'
        if 'priority' in page:
            sitemap_xml += f'    <priority>{page["priority"]:.1f}</priority>\n'
        sitemap_xml += '  </url>\n'
        
    sitemap_xml += '</urlset>'
    return sitemap_xml, 200, {'Content-Type': 'application/xml'}

@main_bp.route('/update_interests', methods=['POST'])
@login_required
def update_interests():
    return jsonify({'success': True, 'message': 'تم تحديث الاهتمامات'})

# ============================================
# ملف التحقق من Google (أبسط حل)
# ============================================
@main_bp.route('/google-site-verification-7Uaxo4sE9avUI6VqAsGp-ldxoslHE10dRIa2Q-Skak0.html')
def google_verification():
    return "google-site-verification=7Uaxo4sE9avUI6VqAsGp-ldxoslHE10dRIa2Q-Skak0"


@main_bp.route('/google314e5a2210182885.html')
def google_verification_new():
    return "google-site-verification: google314e5a2210182885.html"


@main_bp.route('/googleC7pvqXYOiyvCVZLYRAyUb48doCONYF_GTzyQqPSUKfk.html')
def google_verification_fourth():
    return "google-site-verification: googleC7pvqXYOiyvCVZLYRAyUb48doCONYF_GTzyQqPSUKfk.html"

@main_bp.route('/api/users')
@login_required
def api_users():
    """عرض جميع المستخدمين (للمشرفين فقط)"""
    if not current_user.is_admin:
        return jsonify({'error': 'غير مصرح'}), 403
    
    users = User.query.order_by(User.created_at.desc()).all()
    return jsonify([{
        'id': u.id,
        'username': u.username,
        'name': u.name,
        'email': u.email,
        'created_at': u.created_at.isoformat() if u.created_at else None,
        'is_verified': u.is_verified,
        'is_admin': u.is_admin
    } for u in users])
