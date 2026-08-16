import os
import tempfile
from datetime import datetime, timedelta


def login_as(client, user_id):
    with client.session_transaction() as session:
        session['_user_id'] = str(user_id)
        session['_fresh'] = True


def main():
    db_path = os.path.join(tempfile.gettempdir(), 'anter_stories_features_smoke.db')
    try:
        os.remove(db_path)
    except FileNotFoundError:
        pass

    os.environ['DATABASE_URL'] = 'sqlite:///' + db_path
    os.environ['ADMIN_PATH'] = 'admin-stories-smoke'
    from app import create_app, db
    from app.models import User
    from app.models.story import Story, StoryView, StoryReaction

    app = create_app()
    with app.app_context():
        owner = User(username='story_owner', email='owner@example.com', name='صاحب القصة', password_hash='x')
        viewer = User(username='story_viewer', email='viewer@example.com', name='مشاهد القصة', password_hash='x')
        db.session.add_all([owner, viewer])
        db.session.commit()
        story = Story(
            user_id=owner.id,
            media_url='/static/uploads/stories/test.jpg',
            media_type='image',
            expires_at=datetime.utcnow() + timedelta(hours=24),
            is_active=True,
        )
        db.session.add(story)
        db.session.commit()
        story_id, owner_id, viewer_id = story.id, owner.id, viewer.id

    client = app.test_client()
    login_as(client, viewer_id)
    viewed = client.post(f'/api/stories/{story_id}/view')
    assert viewed.status_code == 200, viewed.data
    reacted = client.post(f'/api/stories/{story_id}/react', json={'reaction_type': 'love'})
    assert reacted.status_code == 200, reacted.data
    assert reacted.get_json()['story']['reactions']['love'] == 1

    forbidden = client.get(f'/api/stories/{story_id}/viewers')
    assert forbidden.status_code == 403, forbidden.data

    login_as(client, owner_id)
    viewers = client.get(f'/api/stories/{story_id}/viewers')
    assert viewers.status_code == 200, viewers.data
    payload = viewers.get_json()
    assert payload['views_count'] == 1
    assert payload['viewers'][0]['username'] == 'story_viewer'

    with app.app_context():
        assert StoryView.query.count() == 1
        assert StoryReaction.query.count() == 1

    print('Stories view, reactions, and owner-only viewers API: OK')


if __name__ == '__main__':
    main()
