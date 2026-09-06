from datetime import datetime

from app.extensions import db


class Moment(db.Model):
    __tablename__ = "moments"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    cover_media = db.Column(db.String(500), nullable=True)
    status = db.Column(db.String(20), nullable=False, default="active", index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    expires_at = db.Column(db.DateTime, nullable=True, index=True)

    posts = db.relationship(
        "MomentPost",
        back_populates="moment",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )


class MomentPost(db.Model):
    __tablename__ = "moment_posts"

    id = db.Column(db.Integer, primary_key=True)
    moment_id = db.Column(
        db.Integer,
        db.ForeignKey("moments.id"),
        nullable=False,
        index=True,
    )
    post_id = db.Column(
        db.Integer,
        db.ForeignKey("posts.id"),
        nullable=False,
        index=True,
    )
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    moment = db.relationship("Moment", back_populates="posts")
    post = db.relationship("Post")

    __table_args__ = (
        db.UniqueConstraint(
            "moment_id",
            "post_id",
            name="uq_moment_post",
        ),
    )
