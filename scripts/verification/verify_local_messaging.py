"""Local smoke test for ANTER messaging and notification polling.
Creates temporary SQLite users, exercises the authenticated send route, verifies
its database side effects, and removes only the temporary records afterward.
"""
import uuid

from app import create_app
from app.extensions import db
from app.models import Message, Notification, User

app = create_app()
app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

suffix = uuid.uuid4().hex[:12]
sender_name = f"smoke_sender_{suffix}"
receiver_name = f"smoke_receiver_{suffix}"
message_text = "رسالة فحص محلية للمراسلة"

with app.app_context():
    sender = User(
        username=sender_name,
        email=f"{sender_name}@example.test",
        name="مرسل الفحص",
        password_hash="not-used-by-test",
    )
    receiver = User(
        username=receiver_name,
        email=f"{receiver_name}@example.test",
        name="مستلم الفحص",
        password_hash="not-used-by-test",
    )
    db.session.add_all([sender, receiver])
    db.session.commit()
    sender_id, receiver_id = sender.id, receiver.id

    try:
        with app.test_client() as client:
            with client.session_transaction() as session:
                session['_user_id'] = str(sender_id)
                session['_fresh'] = True

            sent = client.post(
                f'/messages/send/{receiver_id}',
                data={'content': message_text},
                follow_redirects=False,
            )
            assert sent.status_code == 302, sent.status_code
            assert sent.headers['Location'].endswith(f'/messages/{receiver_id}')

            message = Message.query.filter_by(
                sender_id=sender_id,
                receiver_id=receiver_id,
                content=message_text,
            ).one_or_none()
            assert message is not None, 'Message was not stored'

            notification = Notification.query.filter_by(
                user_id=receiver_id,
                actor_id=sender_id,
                action='message',
            ).one_or_none()
            assert notification is not None, 'Notification was not stored'

            count_response = client.get('/sse/notifications')
            assert count_response.status_code == 200, count_response.status_code
            assert count_response.is_json, count_response.content_type
            assert count_response.get_json()['count'] >= 0

        print('PASS: text message, notification, and short-lived notification response work locally.')
    finally:
        Message.query.filter(
            (Message.sender_id.in_([sender_id, receiver_id]))
            | (Message.receiver_id.in_([sender_id, receiver_id]))
        ).delete(synchronize_session=False)
        Notification.query.filter(
            (Notification.user_id.in_([sender_id, receiver_id]))
            | (Notification.actor_id.in_([sender_id, receiver_id]))
        ).delete(synchronize_session=False)
        User.query.filter(User.id.in_([sender_id, receiver_id])).delete(synchronize_session=False)
        db.session.commit()
