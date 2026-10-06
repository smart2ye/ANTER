from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from app.extensions import db, csrf
from app.models import CommentLike, Follow, Like, Post, Comment, Report, Repost, User, UserActivity, Notification
from app.services.anter_user_messages import build_report_resolution_text, build_report_rejection_text
from datetime import datetime, timedelta
from sqlalchemy import func
import os

admin_bp = Blueprint('admin', __name__)


def _public_link(local_link):
    """تحويل رابط محلي إلى الرابط العام (للإرسال الخارجي)."""
    public = current_app.config.get('ANTER_PUBLIC_URL', '').rstrip('/')
    if not public:
        return local_link
    from urllib.parse import urlsplit
    parts = urlsplit(local_link)
    query = ('?' + parts.query) if parts.query else ''
    fragment = ('#' + parts.fragment) if parts.fragment else ''
    return public + parts.path + query + fragment
VERIFICATION_REQUEST_REASON = 'verification:account'
EMAIL_VERIFICATION_REQUEST_REASON = 'verification:email'
PASSWORD_RESET_REQUEST_REASON = 'password-reset-request'
ACCOUNT_REQUEST_REASONS = (
    VERIFICATION_REQUEST_REASON,
    EMAIL_VERIFICATION_REQUEST_REASON,
    PASSWORD_RESET_REQUEST_REASON,
)

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('غير مصرح لك بالدخول إلى لوحة التحكم.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

# ============================================
# لوحة التحكم الرئيسية
# ============================================
@admin_bp.route('/')
@login_required
@admin_required
def dashboard():
    users_count = User.query.count()
    posts_count = Post.query.count()
    comments_count = Comment.query.count()
    reports_count = Report.query.filter_by(status='pending').count()
    post_reactions_count = Like.query.count()
    comment_reactions_count = CommentLike.query.count()
    reposts_count = Repost.query.count()
    interactions_count = (
        post_reactions_count
        + comments_count
        + comment_reactions_count
        + reposts_count
    )

    now = datetime.utcnow()
    online_cutoff = now - timedelta(minutes=5)
    online_count = User.query.filter(
        User.is_active.is_(True),
        User.last_seen >= online_cutoff,
    ).count()
    assistant = User.query.filter_by(
        username=current_app.config.get('ANTER_ASSISTANT_USERNAME', 'anter_assistant'),
        is_active=True,
    ).first()
    if assistant and (not assistant.last_seen or assistant.last_seen < online_cutoff):
        online_count += 1

    follower_counts = (
        db.session.query(
            Follow.followed_id.label('user_id'),
            func.count(Follow.id).label('followers_count'),
        )
        .group_by(Follow.followed_id)
        .subquery()
    )
    top_followed_users = (
        db.session.query(
            User,
            func.coalesce(follower_counts.c.followers_count, 0).label('followers_count'),
        )
        .outerjoin(follower_counts, follower_counts.c.user_id == User.id)
        .order_by(
            func.coalesce(follower_counts.c.followers_count, 0).desc(),
            User.created_at.desc(),
        )
        .limit(5)
        .all()
    )

    activity_since = now - timedelta(days=30)
    activity_counts = (
        db.session.query(
            UserActivity.user_id.label('user_id'),
            func.count(UserActivity.id).label('activity_count'),
        )
        .filter(UserActivity.created_at >= activity_since)
        .group_by(UserActivity.user_id)
        .subquery()
    )
    top_active_users = (
        db.session.query(User, activity_counts.c.activity_count)
        .join(activity_counts, activity_counts.c.user_id == User.id)
        .order_by(activity_counts.c.activity_count.desc(), User.created_at.desc())
        .limit(5)
        .all()
    )

    recent_posts = Post.query.order_by(Post.created_at.desc()).limit(5).all()
    recent_reports = Report.query.filter_by(status='pending').order_by(Report.created_at.desc()).limit(5).all()
    return render_template('admin/dashboard.html',
        users_count=users_count,
        posts_count=posts_count,
        comments_count=comments_count,
        reports_count=reports_count,
        interactions_count=interactions_count,
        online_count=online_count,
        post_reactions_count=post_reactions_count,
        comment_reactions_count=comment_reactions_count,
        reposts_count=reposts_count,
        top_followed_users=top_followed_users,
        top_active_users=top_active_users,
        recent_posts=recent_posts,
        recent_reports=recent_reports
    )

# ============================================
# إدارة المستخدمين (مع CSRF حماية)
# ============================================
@admin_bp.route('/users')
@login_required
@admin_required
def users():
    users_list = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users_list)

@admin_bp.route('/users/toggle/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def toggle_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        return jsonify({'success': False, 'message': 'لا يمكن تعطيل نفسك'})
    user.is_active = not user.is_active
    db.session.commit()
    return jsonify({'success': True, 'is_active': user.is_active})

@admin_bp.route('/users/delete/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        return jsonify({'success': False, 'message': 'لا يمكن حذف نفسك'})
    # ANTER: الحذف المنطقي — لا نحذف الصف فعلياً لتفادي كسر العلاقات.
    # نُعطّل الحساب ونطمس البريد/الهاتف، ونمنع تسجيل الدخول.
    user.is_deleted = True
    user.is_active = False
    user.deleted_at = datetime.utcnow()
    # نُفرغ الهوية الفريدة حتى يستطيع صاحب نفس البريد التسجيل من جديد لو أراد.
    original_email = user.email
    original_phone = user.phone
    user.email = f'deleted-{user.id}-{original_email}'[:120]
    if original_phone:
        user.phone = None
    db.session.commit()
    return jsonify({'success': True})

@admin_bp.route('/users/make_admin/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def make_admin(user_id):
    user = User.query.get_or_404(user_id)
    user.is_admin = not user.is_admin
    db.session.commit()
    return jsonify({'success': True, 'is_admin': user.is_admin})

@admin_bp.route('/users/verify/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def toggle_user_verification(user_id):
    user = User.query.get_or_404(user_id)
    user.is_verified = not user.is_verified
    db.session.commit()
    return jsonify({'success': True, 'is_verified': user.is_verified})


@admin_bp.route('/users/send-email/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def send_email_to_user(user_id):
    from app.utils.email import send_email
    from markupsafe import escape

    user = User.query.get_or_404(user_id)
    if not user.email or user.email.endswith('@phone-only.anter.local'):
        return jsonify({'success': False, 'message': 'لا يوجد بريد إلكتروني صالح لهذا المستخدم.'})

    data = request.get_json(silent=True) or request.form
    subject = (data.get('subject') or '').strip()
    body = (data.get('message') or '').strip()

    if not subject or not body:
        return jsonify({'success': False, 'message': 'الموضوع ونص الرسالة مطلوبان.'})

    # Admin-only: allow raw HTML in body (email body, not rendered on site).
    safe_subject = str(escape(subject))
    html = body

    ok = send_email(user.email, safe_subject, html)
    if ok:
        return jsonify({'success': True, 'message': f'تم إرسال البريد إلى {user.email}'})
    return jsonify({'success': False, 'message': 'فشل إرسال البريد. تحقق من سجلات الخادم.'})


@admin_bp.route('/users/email-verify-link/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def generate_email_verification_link(user_id):
    """توليد رابط تأكيد البريد الإلكتروني لمستخدم معيّن."""
    from app.routes.users import create_email_verification_token

    user = User.query.get_or_404(user_id)
    if not user.email or user.email.endswith('@phone-only.anter.local'):
        return jsonify({'success': False, 'message': 'لا يوجد بريد إلكتروني صالح لهذا المستخدم.'})

    if getattr(user, 'email_verified', False):
        return jsonify({'success': False, 'message': 'البريد الإلكتروني مؤكد بالفعل.'})

    token = create_email_verification_token(user)
    link = _public_link(url_for('users.confirm_email', token=token, _external=True))
    return jsonify({'success': True, 'link': link, 'email': user.email})


@admin_bp.route('/users/password-reset-link/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def generate_password_reset_link(user_id):
    """توليد رابط إعادة تعيين كلمة السر (صالح ساعة، لمرة واحدة)."""
    from app.services.password_reset import generate_token

    user = User.query.get_or_404(user_id)
    token = generate_token(user)
    link = _public_link(url_for('auth.reset_password', token=token, _external=True))
    return jsonify({'success': True, 'link': link, 'email': user.email})

# ============================================
# إدارة المنشورات (مع CSRF حماية)
# ============================================
@admin_bp.route('/posts')
@login_required
@admin_required
def posts():
    posts_list = Post.query.order_by(Post.created_at.desc()).all()
    return render_template('admin/posts.html', posts=posts_list)

@admin_bp.route('/posts/view/<int:post_id>')
@login_required
@admin_required
def view_post(post_id):
    post = Post.query.get_or_404(post_id)
    source = request.args.get('from', '')
    return_destinations = {
        'reports': (url_for('admin.reports'), 'العودة إلى البلاغات'),
        'dashboard': (url_for('admin.dashboard'), 'العودة إلى التحليلات'),
    }
    back_url, back_label = return_destinations.get(source, (url_for('admin.posts'), 'العودة إلى المنشورات'))
    return render_template('admin/post_detail.html', post=post, back_url=back_url, back_label=back_label)

@admin_bp.route('/posts/delete/<int:post_id>', methods=['POST'])
@login_required
@admin_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()
    return jsonify({'success': True})

# ============================================
# نظام البلاغات (مع CSRF حماية)
# ============================================
@admin_bp.route('/videos')
@login_required
@admin_required
def videos():
    from app.models import Video
    videos_list = Video.query.order_by(Video.created_at.desc()).all()
    return render_template('admin/videos.html', videos=videos_list)


@admin_bp.route('/videos/delete/<int:video_id>', methods=['POST'])
@login_required
@admin_required
def delete_video_admin(video_id):
    from app.models import Video
    video = Video.query.get_or_404(video_id)
    db.session.delete(video)
    db.session.commit()
    return jsonify({'success': True})


@admin_bp.route('/reports')
@login_required
@admin_required
def reports():
    import re
    reports_list = Report.query.order_by(Report.created_at.desc()).all()

    # استخراج اسم المستخدم المُبلَّغ عنه من تفاصيل بلاغات المستخدمين
    user_report_targets = {}
    for r in reports_list:
        if r.reason and r.reason.startswith('user-report:'):
            m = re.search(r'\[بلاغ عن مستخدم:\s*([^\]\s]+)\]', r.details or '')
            if m:
                username = m.group(1).strip()
                target = User.query.filter_by(username=username).first()
                if target:
                    user_report_targets[r.id] = {
                        'username': target.username,
                        'name': target.name or target.username,
                        'avatar_id': target.id,
                    }
                    continue
            user_report_targets[r.id] = {
                'username': username if 'username' in locals() else '?',
                'name': 'مستخدم محذوف',
                'avatar_id': None,
            }

    return render_template(
        'admin/reports.html',
        reports=reports_list,
        user_report_targets=user_report_targets,
    )


@admin_bp.route('/support-requests')
@login_required
@admin_required
def support_requests():
    requests = Report.query.filter(
        Report.reason.startswith('support:')
    ).order_by(Report.created_at.desc()).all()
    return render_template('admin/support_requests.html', requests=requests)


@admin_bp.route('/verification-requests')
@login_required
@admin_required
def verification_requests():
    requests = Report.query.filter(
        Report.reason.in_(ACCOUNT_REQUEST_REASONS),
    ).order_by(Report.created_at.desc()).all()
    return render_template('admin/verification_requests.html', requests=requests)


@admin_bp.route('/verification-requests/<int:request_id>/approve', methods=['POST'])
@login_required
@admin_required
def approve_verification_request(request_id):
    verification_request = Report.query.filter_by(
        id=request_id,
        reason=VERIFICATION_REQUEST_REASON,
    ).first_or_404()
    if verification_request.status != 'pending':
        return jsonify({'success': False, 'message': 'تمت مراجعة هذا الطلب بالفعل.'}), 409

    applicant = verification_request.reporter
    applicant.is_verified = True
    verification_request.status = 'resolved'
    verification_request.resolved_at = datetime.utcnow()
    verification_request.resolved_by = current_user.id
    db.session.add(Notification(
        user_id=applicant.id,
        actor_id=current_user.id,
        action='verification_approved',
    ))
    db.session.commit()
    return jsonify({'success': True, 'is_verified': True})


@admin_bp.route('/account-requests/<int:request_id>/email-link', methods=['POST'])
@login_required
@admin_required
def create_email_verification_link_for_request(request_id):
    """توليد رابط تأكيد البريد لصاحب الطلب (لا يُرسَل تلقائيًا)."""
    from app.routes.users import create_email_verification_token

    req = Report.query.filter_by(
        id=request_id,
        reason=EMAIL_VERIFICATION_REQUEST_REASON,
    ).first_or_404()

    if req.status != 'pending':
        return jsonify({'success': False, 'message': 'تمت مراجعة هذا الطلب بالفعل.'}), 409

    applicant = req.reporter
    if not applicant:
        return jsonify({'success': False, 'message': 'المستخدم غير موجود.'})

    if applicant.email_verified:
        req.status = 'resolved'
        req.resolved_at = datetime.utcnow()
        req.resolved_by = current_user.id
        db.session.commit()
        return jsonify({'success': False, 'message': 'البريد مؤكد بالفعل.'})

    token = create_email_verification_token(applicant)
    link = url_for('users.confirm_email', token=token, _external=True)

    # وسيلة التواصل لعرضها للأدمن (البريد إن وُجد، أو الجوال).
    contact = ''
    if applicant.email and not applicant.email.endswith('@phone-only.anter.local'):
        contact = applicant.email
    elif applicant.phone:
        contact = applicant.phone
    elif applicant.username:
        contact = f'@{applicant.username}'

    req.status = 'resolved'
    req.resolved_at = datetime.utcnow()
    req.resolved_by = current_user.id
    db.session.commit()

    return jsonify({'success': True, 'link': link, 'email': contact})


@admin_bp.route('/account-requests/<int:request_id>/password-link', methods=['POST'])
@login_required
@admin_required
def create_password_reset_link_for_request(request_id):
    """توليد رابط إعادة تعيين كلمة السر لصاحب الطلب (لا يُرسَل تلقائيًا)."""
    from itsdangerous import URLSafeTimedSerializer

    req = Report.query.filter_by(
        id=request_id,
        reason=PASSWORD_RESET_REQUEST_REASON,
    ).first_or_404()

    if req.status != 'pending':
        return jsonify({'success': False, 'message': 'تمت مراجعة هذا الطلب بالفعل.'}), 409

    applicant = req.reporter
    if not applicant:
        return jsonify({'success': False, 'message': 'المستخدم غير موجود.'})

    from app.services.password_reset import generate_token
    token = generate_token(applicant)
    link = url_for('auth.reset_password', token=token, _external=True)

    req.status = 'resolved'
    req.resolved_at = datetime.utcnow()
    req.resolved_by = current_user.id
    db.session.commit()

    return jsonify({'success': True, 'link': link, 'email': applicant.email or '(no email)'})


@admin_bp.route('/account-requests/<int:request_id>/reject', methods=['POST'])
@login_required
@admin_required
def reject_account_request(request_id):
    """رفض طلب (تأكيد بريد أو إعادة كلمة السر)."""
    req = Report.query.filter(
        Report.id == request_id,
        Report.reason.in_((EMAIL_VERIFICATION_REQUEST_REASON, PASSWORD_RESET_REQUEST_REASON)),
    ).first_or_404()

    if req.status != 'pending':
        return jsonify({'success': False, 'message': 'تمت مراجعة هذا الطلب بالفعل.'}), 409

    req.status = 'rejected'
    req.resolved_at = datetime.utcnow()
    req.resolved_by = current_user.id
    db.session.commit()
    return jsonify({'success': True})


@admin_bp.route('/verification-requests/<int:request_id>/reject', methods=['POST'])
@login_required
@admin_required
def reject_verification_request(request_id):
    verification_request = Report.query.filter_by(
        id=request_id,
        reason=VERIFICATION_REQUEST_REASON,
    ).first_or_404()
    if verification_request.status != 'pending':
        return jsonify({'success': False, 'message': 'تمت مراجعة هذا الطلب بالفعل.'}), 409

    verification_request.status = 'rejected'
    verification_request.resolved_at = datetime.utcnow()
    verification_request.resolved_by = current_user.id
    db.session.add(Notification(
        user_id=verification_request.reporter_id,
        actor_id=current_user.id,
        action='verification_rejected',
    ))
    db.session.commit()
    return jsonify({'success': True, 'is_verified': False})

@admin_bp.route('/reports/resolve/<int:report_id>', methods=['POST'])
@login_required
@admin_required
def resolve_report(report_id):
    report = Report.query.get_or_404(report_id)
    report.status = 'resolved'
    report.resolved_at = datetime.utcnow()
    report.resolved_by = current_user.id

    # إشعار للمُبلِّغ بأن البلاغ حُلّ (نتجاهل بلاغات النظام أو بلاغات المستخدم عن نفسه)
    try:
        if report.reporter_id and report.reporter_id != current_user.id:
            db.session.add(Notification(
                user_id=report.reporter_id,
                actor_id=current_user.id,
                action='report_resolved',
                report_id=report.id,
                extra_text='تمت مراجعة بلاغك واتخاذ الإجراء المناسب. اضغط للاطلاع على التفاصيل الكاملة.',
            ))
            # نص كامل يُخزَّن في التقرير (يظهر في تبويب «المساعدة والدعم»)
            reporter = User.query.get(report.reporter_id)
            if reporter:
                report.resolution_note = build_report_resolution_text(reporter, report)
    except Exception:
        current_app.logger.warning('تعذر إرسال رسالة حل البلاغ', exc_info=True)

    db.session.commit()
    return jsonify({'success': True})

@admin_bp.route('/reports/reject/<int:report_id>', methods=['POST'])
@login_required
@admin_required
def reject_report(report_id):
    report = Report.query.get_or_404(report_id)
    data = request.get_json(silent=True) or {}
    rejection_reason = (data.get('reason') or '').strip()[:500]

    report.status = 'rejected'
    report.resolved_at = datetime.utcnow()
    report.resolved_by = current_user.id
    report.rejection_reason = rejection_reason or None

    # إشعار للمُبلِّغ بسبب الرفض
    try:
        if report.reporter_id and report.reporter_id != current_user.id:
            text = 'لم يُتخذ إجراء بشأن بلاغك.'
            if rejection_reason:
                text = f'تم رفض بلاغك. السبب: {rejection_reason}'
            db.session.add(Notification(
                user_id=report.reporter_id,
                actor_id=current_user.id,
                action='report_rejected',
                report_id=report.id,
                extra_text=text[:500],
            ))
            # نص كامل يُخزَّن في التقرير (يظهر في تبويب «المساعدة والدعم»)
            reporter = User.query.get(report.reporter_id)
            if reporter:
                report.resolution_note = build_report_rejection_text(reporter, report, rejection_reason)
    except Exception:
        current_app.logger.warning('تعذر إرسال رسالة رفض البلاغ', exc_info=True)

    db.session.commit()
    return jsonify({'success': True})

@admin_bp.route('/reports/delete/<int:report_id>', methods=['POST'])
@login_required
@admin_required
def delete_report(report_id):
    report = Report.query.get_or_404(report_id)
    db.session.delete(report)
    db.session.commit()
    return jsonify({'success': True})
