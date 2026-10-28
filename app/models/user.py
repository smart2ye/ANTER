from app.extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from app.models.follow import Follow

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    bio = db.Column(db.String(200), default='')
    avatar = db.Column(db.String(200), default='default.png')
    avatar_data = db.Column(db.LargeBinary, nullable=True)
    avatar_mime = db.Column(db.String(100), nullable=True)
    
    gender = db.Column(db.String(20), default='')
    birth_date = db.Column(db.Date, nullable=True)
    is_private = db.Column(db.Boolean, default=False)
    profile_visibility = db.Column(db.String(20), default='public', nullable=False)
    # من يستطيع الكتابة على حائطي:
    #   public    = أي مستخدم مسجّل
    #   followers = المتابعون فقط
    #   mutual    = المتابعة المتبادلة فقط
    #   none      = الحائط مغلق
    wall_visibility = db.Column(
        db.String(20),
        default='public',
        nullable=False,
        server_default='public',
    )
    hide_followers = db.Column(db.Boolean, default=False)
    show_online_status = db.Column(db.Boolean, default=True, nullable=False)
    show_email = db.Column(db.Boolean, default=False)
    message_privacy = db.Column(db.String(20), default='everyone')
    # ANTER: من يستطيع الإشارة إليّ (@mention) — everyone / followers_only / nobody
    mention_privacy = db.Column(
        db.String(20), nullable=False, default='followers_only',
        server_default='followers_only', index=True,
    )
    
    # 🔹 إضافة عمود is_admin
    # ANTER Haraj: رقم واتساب افتراضي للحراج + خيار الإظهار
    haraj_whatsapp_number = db.Column(db.String(20), nullable=True)
    haraj_show_whatsapp = db.Column(
        db.Boolean, nullable=False, default=False, server_default='false',
    )

    is_admin = db.Column(db.Boolean, default=False)
    is_verified = db.Column(db.Boolean, default=False)
    # ANTER: نظام الإحالة — كود فريد، مَن دعاه، عدد الإحالات المكتملة
    referral_code = db.Column(db.String(12), unique=True, nullable=True, index=True)
    referred_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    referral_count = db.Column(db.Integer, nullable=False, default=0, server_default='0')
    referral_credited = db.Column(db.Boolean, nullable=False, default=False, server_default='false')
    # ANTER: مسار التوثيق — المصدر (admin/assistant/referral/progress) + قفل الإدارة
    verification_source = db.Column(db.String(20), nullable=True)
    verification_locked = db.Column(db.Boolean, nullable=False, default=False, server_default='false')
    # ANTER: شارة المؤسس — خاصة بحساب واحد فقط.
    is_founder = db.Column(db.Boolean, nullable=False, default=False, server_default='false', index=True)
    # ANTER: عضو مبكّر — أول من آمن بالمنصة.
    is_early_member = db.Column(db.Boolean, nullable=False, default=False, server_default='false', index=True)
    
    # ANTER: نظام العقوبات المتدرجة
    warning_count = db.Column(db.Integer, nullable=False, default=0, server_default='0')
    last_warning_at = db.Column(db.DateTime, nullable=True)
    suspended_until = db.Column(db.DateTime, nullable=True)
    restricted_until = db.Column(db.DateTime, nullable=True)
    is_banned = db.Column(db.Boolean, nullable=False, default=False, server_default='false')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    country_code = db.Column(db.String(10), default='+966')
    phone = db.Column(db.String(20), unique=True, nullable=True, index=True)
    phone_verified = db.Column(db.Boolean, default=False)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    theme_preference = db.Column(db.String(20), default='light')
    terms_agreed = db.Column(db.Boolean, default=False)

    # ANTER: الحذف المنطقي — لا نحذف صفوف المستخدم فعلياً (لتجنّب كسر العلاقات).
    is_deleted = db.Column(db.Boolean, nullable=False, default=False, server_default='false', index=True)
    deleted_at = db.Column(db.DateTime, nullable=True)

    # العلاقات
    posts = db.relationship(
        'Post',
        foreign_keys='Post.author_id',
        backref='author',
        lazy='dynamic',
        cascade='all, delete-orphan',
    )
    comments = db.relationship('Comment', backref='author', lazy='dynamic', cascade='all, delete-orphan')
    messages_sent = db.relationship('Message', foreign_keys='Message.sender_id', backref='sender', lazy='dynamic')
    messages_received = db.relationship('Message', foreign_keys='Message.receiver_id', backref='receiver', lazy='dynamic')
    notifications = db.relationship('Notification', foreign_keys='Notification.user_id', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    following = db.relationship('Follow', foreign_keys='Follow.follower_id', backref='follower', lazy='dynamic', cascade='all, delete-orphan')
    followers = db.relationship('Follow', foreign_keys='Follow.followed_id', backref='followed', lazy='dynamic', cascade='all, delete-orphan')
    likes = db.relationship('Like', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    # ANTER: الإحالة — علاقة ذاتية (مَن دعاني / مَن دعوت)
    referred_by = db.relationship(
        'User',
        remote_side='User.id',
        foreign_keys='User.referred_by_id',
        backref=db.backref('referred_users', lazy='dynamic'),
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def follow(self, user):
        if not self.is_following(user):
            f = Follow(follower_id=self.id, followed_id=user.id)
            db.session.add(f)
            db.session.commit()

    def unfollow(self, user):
        f = Follow.query.filter_by(follower_id=self.id, followed_id=user.id).first()
        if f:
            db.session.delete(f)
            db.session.commit()

    def is_following(self, user):
        return Follow.query.filter_by(follower_id=self.id, followed_id=user.id).first() is not None

    def follower_count(self):
        return self.followers.count()

    def following_count(self):
        return self.following.count()

    def get_age(self):
        if self.birth_date:
            today = datetime.now().date()
            return today.year - self.birth_date.year - ((today.month, today.day) < (self.birth_date.month, self.birth_date.day))
        return None

    def __repr__(self):
        return f'<User {self.username}>'
