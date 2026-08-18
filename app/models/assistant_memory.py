"""ذاكرة محلية خاصة بمحادثات مساعد أنتر.

تخزّن تفضيلات صريحة وملخصاً قصيراً من رسائل المستخدم داخل قاعدة بيانات ANTER.
لا تُرسل هذه البيانات إلى أي خدمة خارجية ولا تحل محل سجل الرسائل.
"""

from datetime import datetime

from app.extensions import db


class AssistantMemory(db.Model):
    """ذاكرة مقيدة لمستخدم واحد مع حساب مساعد أنتر الواحد."""

    __tablename__ = "assistant_memories"

    id = db.Column(db.Integer, primary_key=True)
    assistant_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    preferences_json = db.Column(db.Text, nullable=False, default="[]")
    recent_context_json = db.Column(db.Text, nullable=False, default="[]")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    __table_args__ = (
        db.UniqueConstraint(
            "assistant_id",
            "user_id",
            name="uq_assistant_memory_user_pair",
        ),
    )

    def __repr__(self):
        return f"<AssistantMemory assistant={self.assistant_id} user={self.user_id}>"
