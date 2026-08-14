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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)

    def __repr__(self):
        return f'<Message {self.id}>'
