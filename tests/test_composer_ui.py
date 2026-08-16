import os
import tempfile


def main():
    db_path = os.path.join(tempfile.gettempdir(), 'anter_composer_ui_smoke.db')
    try:
        os.remove(db_path)
    except FileNotFoundError:
        pass

    os.environ['DATABASE_URL'] = 'sqlite:///' + db_path
    os.environ['ADMIN_PATH'] = 'admin-composer-smoke'
    from app import create_app, db
    from app.models import User

    app = create_app()
    with app.app_context():
        user = User(
            username='composer_user',
            email='composer@example.com',
            name='كاتب ANTER',
            password_hash='x',
        )
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = str(user_id)
        session['_fresh'] = True

    response = client.get('/')
    assert response.status_code == 200, response.data
    content = response.get_data(as_text=True)
    for marker in ('quick-composer-card', 'quickPostModal', 'quickImageDropZone', 'quickLinkHint', 'quickPostSubmit'):
        assert marker in content, f'Missing composer UI marker: {marker}'

    print('Quick post composer UI render: OK')


if __name__ == '__main__':
    main()
