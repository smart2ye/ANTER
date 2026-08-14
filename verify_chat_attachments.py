from io import BytesIO
from pathlib import Path

from app import create_app
from app.extensions import db
from app.models import Message, User

app = create_app()

with app.app_context():
    users = User.query.order_by(User.id.asc()).limit(2).all()
    if len(users) < 2:
        raise SystemExit('Need at least two local users for attachment test')
    sender, receiver = users[0], users[1]


def logged_client(user_id):
    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = str(user_id)
        session['_fresh'] = True
    return client

client = logged_client(sender.id)
response = client.post(
    f'/messages/send/{receiver.id}',
    data={
        'content': 'اختبار مرفق محادثة',
        'attachment': (BytesIO(b'ANTER chat attachment test'), 'test.txt'),
    },
    content_type='multipart/form-data',
)
print('send:', response.status_code, response.location)

with app.app_context():
    message = Message.query.filter_by(
        sender_id=sender.id,
        receiver_id=receiver.id,
        attachment_name='test.txt',
    ).order_by(Message.id.desc()).first()
    if not message:
        raise SystemExit('attachment message was not stored')
    message_id = message.id
    print('stored:', message_id, message.attachment_kind, message.attachment_mime, len(message.attachment_data or b''))

served = client.get(f'/messages/attachment/{message_id}')
print('served:', served.status_code, served.mimetype, served.data)

image_path = Path(app.root_path) / 'static' / 'uploads' / 'default.png'
image_response = client.post(
    f'/messages/send/{receiver.id}',
    data={
        'content': 'اختبار صورة مرفقة',
        'attachment': (BytesIO(image_path.read_bytes()), 'test.png'),
    },
    content_type='multipart/form-data',
)
with app.app_context():
    image_message = Message.query.filter_by(
        sender_id=sender.id,
        receiver_id=receiver.id,
        attachment_name='test.png',
    ).order_by(Message.id.desc()).first()
    if not image_message:
        raise SystemExit('image attachment message was not stored')
    image_id = image_message.id
image_served = client.get(f'/messages/attachment/{image_id}')
print('image-served:', image_served.status_code, image_served.mimetype, len(image_served.data))

if response.status_code != 302 or image_response.status_code != 302:
    raise SystemExit('multipart send did not redirect normally')
if served.status_code != 200 or served.data != b'ANTER chat attachment test':
    raise SystemExit('attachment was not served correctly')
if served.headers.get('Content-Disposition', '').startswith('inline'):
    raise SystemExit('generic file must not be served inline')
if image_served.status_code != 200 or not image_served.mimetype.startswith('image/'):
    raise SystemExit('image attachment was not served correctly')
if not image_served.headers.get('Content-Disposition', '').startswith('inline'):
    raise SystemExit('image attachment must be served inline')
print('attachment-test=ok')
