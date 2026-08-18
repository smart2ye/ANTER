"""سجل منشورات مساعد أنتر اليومية لمنع النشر المكرر."""

from datetime import date, datetime

from app.extensions import db


class AssistantDailyPublication(db.Model):
    __tablename__ = "assistant_daily_publications"

    id = db.Column(db.Integer, primary_key=True)
    published_on = db.Column(db.Date, nullable=False, unique=True, index=True, default=date.today)
    post_id = db.Column(db.Integer, db.ForeignKey("posts.id"), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    post = db.relationship("Post", lazy="joined")

    def __repr__(self):
        return f"<AssistantDailyPublication day={self.published_on} post={self.post_id}>"
