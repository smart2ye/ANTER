import os
from datetime import datetime
from flask import current_app
from app import db
from app.models.story import Story

def delete_expired_stories(app_instance):
    with app_instance.app_context():
        now = datetime.utcnow()
        expired_stories = Story.query.filter(Story.expires_at < now).all()
        for story in expired_stories:
            story.is_active = False
            try:
                if story.media_url and story.media_url.startswith('/static/uploads/'):
                    filepath = os.path.join(current_app.root_path, story.media_url.lstrip('/'))
                    if os.path.exists(filepath):
                        os.remove(filepath)
            except Exception:
                pass
            db.session.delete(story)
        db.session.commit()
