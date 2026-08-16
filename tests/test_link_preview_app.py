import os
import tempfile


def main():
    db_path = os.path.join(tempfile.gettempdir(), 'anter_link_preview_smoke.db')
    try:
        os.remove(db_path)
    except FileNotFoundError:
        pass

    os.environ['DATABASE_URL'] = 'sqlite:///' + db_path
    os.environ['ADMIN_PATH'] = 'admin-smoke-test'
    from app import create_app
    from app.models import Post

    app = create_app()
    app.jinja_env.get_template('_post_card.html')
    with app.app_context():
        columns = {column.name for column in Post.__table__.columns}
        required = {'link_url', 'link_title', 'link_description', 'link_image'}
        missing = required - columns
        if missing:
            raise AssertionError(f'Missing Post columns: {sorted(missing)}')
    print('Flask startup and Post link-preview columns: OK')


if __name__ == '__main__':
    main()
