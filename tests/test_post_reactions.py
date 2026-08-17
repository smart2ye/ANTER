import os
import tempfile


def login_as(client, user_id):
    with client.session_transaction() as session:
        session['_user_id'] = str(user_id)
        session['_fresh'] = True


def main():
    db_path = os.path.join(tempfile.gettempdir(), 'anter_post_reactions_smoke.db')
    try:
        os.remove(db_path)
    except FileNotFoundError:
        pass

    os.environ['DATABASE_URL'] = 'sqlite:///' + db_path
    os.environ['ADMIN_PATH'] = 'admin-reactions-smoke'
    from app import create_app, db
    from app.models import Post, User

    app = create_app()
    with app.app_context():
        author = User(username='reaction_author', email='author@example.com', name='كاتب', password_hash='x')
        reactor = User(username='reaction_user', email='reactor@example.com', name='متفاعل', password_hash='x')
        db.session.add_all([author, reactor])
        db.session.commit()
        post = Post(content='اختبار التفاعلات', author_id=author.id)
        db.session.add(post)
        db.session.commit()
        post_id, reactor_id = post.id, reactor.id

    client = app.test_client()
    login_as(client, reactor_id)

    love = client.post(f'/like/{post_id}', json={'reaction': 'love'})
    assert love.status_code == 200, love.data
    love_data = love.get_json()
    assert love_data['liked'] is True
    assert love_data['reaction'] == 'love'
    assert love_data['count'] == 1
    assert love_data['reaction_counts']['love'] == 1

    haha = client.post(f'/like/{post_id}', json={'reaction': 'haha'})
    assert haha.status_code == 200, haha.data
    haha_data = haha.get_json()
    assert haha_data['liked'] is True
    assert haha_data['reaction'] == 'haha'
    assert haha_data['count'] == 1
    assert haha_data['reaction_counts']['love'] == 0
    assert haha_data['reaction_counts']['haha'] == 1

    removed = client.post(f'/like/{post_id}', json={'reaction': 'haha'})
    assert removed.status_code == 200, removed.data
    removed_data = removed.get_json()
    assert removed_data['liked'] is False
    assert removed_data['count'] == 0
    assert sum(removed_data['reaction_counts'].values()) == 0

    print('Post reaction toggle and reaction-count distribution: OK')


if __name__ == '__main__':
    main()
