from app.extensions import db
from datetime import datetime
import json


ACTION_LABELS = {
    'registration': 'إنشاء الحساب',
    'login': 'تسجيل الدخول',
    'logout': 'تسجيل الخروج',
    'password_change': 'تغيير كلمة المرور',
    'profile_update': 'تحديث الملف الشخصي',
    'settings_update': 'تحديث إعدادات الحساب',
    'username_change': 'تغيير اسم المستخدم',
    'email_change': 'تغيير البريد الإلكتروني',
    'phone_change': 'تغيير رقم الجوال',
    'avatar_change': 'تغيير صورة الملف الشخصي',
    'follow': 'متابعة مستخدم',
    'unfollow': 'إلغاء متابعة مستخدم',
    'post_create': 'نشر منشور',
    'post_edit': 'تعديل منشور',
    'post_delete': 'حذف منشور',
    'post_reaction_add': 'إضافة تفاعل',
    'post_reaction_remove': 'إزالة تفاعل',
    'comment_create': 'إضافة تعليق',
    'comment_reaction_add': 'الإعجاب بتعليق',
    'comment_reaction_remove': 'إزالة الإعجاب عن تعليق',
    'repost_add': 'إعادة نشر منشور',
    'repost_remove': 'إلغاء إعادة النشر',
    'report_create': 'إرسال بلاغ',
    'post_hide': 'إخفاء منشور',
    'story_create': 'نشر قصة',
    'story_delete': 'حذف قصة',
    'story_view': 'مشاهدة قصة',
    'story_reaction_add': 'إضافة تفاعل على قصة',
    'story_reaction_remove': 'إزالة تفاعل عن قصة',
    'video_upload': 'رفع فيديو',
    'video_reaction_add': 'الإعجاب بفيديو',
    'video_reaction_remove': 'إزالة الإعجاب عن فيديو',
    'video_comment_create': 'إضافة تعليق على فيديو',
    'video_comment_reaction_add': 'الإعجاب بتعليق فيديو',
    'video_comment_reaction_remove': 'إزالة الإعجاب عن تعليق فيديو',
    'download_data': 'تنزيل بيانات الحساب',
}

class UserActivity(db.Model):
    __tablename__ = 'user_activities'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    action = db.Column(db.String(50), nullable=False)
    ip_address = db.Column(db.String(50))
    user_agent = db.Column(db.Text)
    browser = db.Column(db.String(50))
    os = db.Column(db.String(50))
    device_type = db.Column(db.String(50))
    details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('activities', lazy='dynamic', cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<UserActivity {self.user_id} - {self.action}>'

    @property
    def action_label(self):
        return ACTION_LABELS.get(self.action, self.action.replace('_', ' '))

    @property
    def public_details(self):
        try:
            values = json.loads(self.details or '{}')
        except (TypeError, ValueError):
            return ''
        if not isinstance(values, dict):
            return ''
        if values.get('fields'):
            return 'تغييرات: ' + '، '.join(str(item) for item in values['fields'])
        if values.get('target_username'):
            return '@' + str(values['target_username'])
        if values.get('reaction'):
            return 'التفاعل: ' + str(values['reaction'])
        if values.get('post_id'):
            return 'منشور #' + str(values['post_id'])
        return ''
