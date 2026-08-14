from app import create_app
from app.extensions import db
from app.models import Comment, Notification, Post, User

app = create_app()

with app.app_context():
    users = User.query.order_by(User.id.asc()).all()
    post = Post.query.order_by(Post.id.asc()).first()
    if not post:
        raise SystemExit('Need one post for the comment test')
    author = db.session.get(User, post.author_id)
    commenter = next((user for user in users if user.id != author.id), None)
    if not author or not commenter:
        raise SystemExit('Need two different users and one post for the comment test')

client = app.test_client()
with client.session_transaction() as session:
    session['_user_id'] = str(commenter.id)
    session['_fresh'] = True

response = client.post(
    f'/comment/{post.id}',
    data={'content': 'اختبار نشر تعليق بعد إصلاح الإشعار'},
    follow_redirects=False,
)
print('comment:', response.status_code, response.location)

with app.app_context():
    comment = Comment.query.filter_by(
        post_id=post.id,
        author_id=commenter.id,
        content='اختبار نشر تعليق بعد إصلاح الإشعار',
    ).order_by(Comment.id.desc()).first()
    notification = Notification.query.filter_by(
        user_id=author.id,
        actor_id=commenter.id,
        action='comment',
        post_id=post.id,
    ).order_by(Notification.id.desc()).first()
    print('stored:', bool(comment), bool(notification))

if response.status_code != 302 or not comment or not notification:
    raise SystemExit('comment notification test failed')
print('comment-test=ok')
