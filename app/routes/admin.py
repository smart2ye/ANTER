from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from app.extensions import db, csrf
from app.models import User, Post, Comment, Report, Notification
from datetime import datetime
import os

admin_bp = Blueprint('admin', __name__)

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
    recent_posts = Post.query.order_by(Post.created_at.desc()).limit(5).all()
    recent_reports = Report.query.filter_by(status='pending').order_by(Report.created_at.desc()).limit(5).all()
    return render_template('admin/dashboard.html',
        users_count=users_count,
        posts_count=posts_count,
        comments_count=comments_count,
        reports_count=reports_count,
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
    db.session.delete(user)
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
    return render_template('admin/post_detail.html', post=post)

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
@admin_bp.route('/reports')
@login_required
@admin_required
def reports():
    reports_list = Report.query.order_by(Report.created_at.desc()).all()
    return render_template('admin/reports.html', reports=reports_list)

@admin_bp.route('/reports/resolve/<int:report_id>', methods=['POST'])
@login_required
@admin_required
def resolve_report(report_id):
    report = Report.query.get_or_404(report_id)
    report.status = 'resolved'
    report.resolved_at = datetime.utcnow()
    report.resolved_by = current_user.id
    db.session.commit()
    return jsonify({'success': True})

@admin_bp.route('/reports/reject/<int:report_id>', methods=['POST'])
@login_required
@admin_required
def reject_report(report_id):
    report = Report.query.get_or_404(report_id)
    report.status = 'rejected'
    report.resolved_at = datetime.utcnow()
    report.resolved_by = current_user.id
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
