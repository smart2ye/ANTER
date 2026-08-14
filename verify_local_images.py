"""Smoke test for durable avatar and post image storage."""
from pathlib import Path
import uuid

from app import create_app
from app.extensions import db
from app.models import Post, User
from app.utils.image_storage import prepare_image_data

app = create_app()
app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
image_path = Path('/home/ubuntu/ANTER/anter-helper-avatar.png')

with app.app_context():
    avatar_data, avatar_mime = prepare_image_data(
        type('Upload', (), {'filename': image_path.name, 'read': lambda self, n=-1: image_path.read_bytes()})()
    )
    assert avatar_data and avatar_mime == 'image/png'

    suffix = uuid.uuid4().hex[:12]
    user = User(
        username=f'image_smoke_{suffix}',
        email=f'image_smoke_{suffix}@example.test',
        name='اختبار الصور',
        password_hash='not-used-by-test',
        avatar_data=avatar_data,
        avatar_mime=avatar_mime,
    )
    db.session.add(user)
    db.session.flush()
    post = Post(
        content='اختبار صورة منشور دائمة',
        author_id=user.id,
        image_data=avatar_data,
        image_mime=avatar_mime,
    )
    db.session.add(post)
    db.session.commit()
    user_id, post_id = user.id, post.id

    try:
        with app.test_client() as client:
            with client.session_transaction() as session:
                session['_user_id'] = str(user_id)
                session['_fresh'] = True

            profile = client.get(f'/users/{user.username}')
            assert profile.status_code == 200, profile.status_code
            assert f'/media/avatar/{user_id}' in profile.get_data(as_text=True)
            assert f'/media/post/{post_id}' in profile.get_data(as_text=True)

            avatar_response = client.get(f'/media/avatar/{user_id}')
            assert avatar_response.status_code == 200
            assert avatar_response.content_type.startswith('image/png')
            assert len(avatar_response.data) == len(avatar_data)

            post_response = client.get(f'/media/post/{post_id}')
            assert post_response.status_code == 200
            assert post_response.content_type.startswith('image/png')
            assert len(post_response.data) == len(avatar_data)

        print('PASS: durable avatar/post image data renders and serves locally.')
    finally:
        db.session.delete(post)
        db.session.delete(user)
        db.session.commit()
