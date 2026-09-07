import os
import tempfile

import pytest

from app import create_app
from app.extensions import db


@pytest.fixture
def app():
    """Create a Flask application isolated from the development database."""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    database_uri = f"sqlite:///{db_path}"

    try:
        app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": database_uri,
            "STARTUP_SCHEMA_UPGRADES_ENABLED": True,
        })

        with app.app_context():
            db.drop_all()
            db.create_all()

        yield app

    finally:
        with app.app_context():
            db.session.remove()

        db.engine.dispose()

        try:
            os.remove(db_path)
        except FileNotFoundError:
            pass


@pytest.fixture
def client(app):
    """HTTP test client using the isolated test database."""
    return app.test_client()


@pytest.fixture
def db_session(app):
    """Database session bound to the isolated test database."""
    with app.app_context():
        yield db.session
        db.session.rollback()
