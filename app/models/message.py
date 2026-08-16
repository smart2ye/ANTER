from app.extensions import db
from datetime import datetime

class Message(db.Model):
    __tablename__ = 'messages'

    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False, default='')
    # الاحتفاظ بـ audio_path للتوافق مع الرسائل القديمة، وتخزين الصوت الجديد
    # في قاعدة البيانات لتفادي فقدان/فشل ملفات الرفع في بيئات الإنتاج المؤقتة.
    audio_path = db.Column(db.String(255), nullable=True)
    audio_data = db.Column(db.LargeBinary, nullable=True)
    audio_mime = db.Column(db.String(100), nullable=True)
    attachment_data = db.Column(db.LargeBinary, nullable=True)
    attachment_mime = db.Column(db.String(150), nullable=True)
    attachment_name = db.Column(db.String(255), nullable=True)
    attachment_kind = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    # ميزات متقدمة
    parent_id = db.Column(db.Integer, db.ForeignKey('messages.id'), nullable=True) # للرد على رسالة
    is_deleted_everyone = db.Column(db.Boolean, default=False) # حذف عند الطرفين
    deleted_by_sender = db.Column(db.Boolean, default=False) # حذف عند المرسل فقط
    deleted_by_receiver = db.Column(db.Boolean, default=False) # حذف عند المستلم فقط

    # العلاقات
    replies = db.relationship('Message', backref=db.backref('parent', remote_side=[id]), lazy='dynamic')

    def __repr__(self):
        return f'<Message {self.id}>'
