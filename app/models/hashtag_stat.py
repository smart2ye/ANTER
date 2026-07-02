from app.extensions import db
from datetime import datetime

class HashtagStat(db.Model):
    __tablename__ = 'hashtag_stats'
    
    id = db.Column(db.Integer, primary_key=True)
    hashtag_id = db.Column(db.Integer, db.ForeignKey('hashtags.id'), nullable=False, index=True)
    date = db.Column(db.Date, default=datetime.utcnow, index=True)
    
    posts_count = db.Column(db.Integer, default=0)  # عدد المنشورات اليومي
    likes_count = db.Column(db.Integer, default=0)  # عدد الإعجابات اليومي
    comments_count = db.Column(db.Integer, default=0)  # عدد التعليقات اليومي
    
    __table_args__ = (db.UniqueConstraint('hashtag_id', 'date', name='unique_hashtag_stat'),)
    
    hashtag = db.relationship('Hashtag', backref='stats')
    
    @staticmethod
    def record_usage(hashtag_id):
        """تسجيل استخدام وسم جديد"""
        from datetime import date
        stat = HashtagStat.query.filter_by(
            hashtag_id=hashtag_id,
            date=date.today()
        ).first()
        if not stat:
            stat = HashtagStat(hashtag_id=hashtag_id)
            db.session.add(stat)
        stat.posts_count += 1
        db.session.commit()
    
    def __repr__(self):
        return f'<HashtagStat {self.hashtag_id}-{self.date}>'
