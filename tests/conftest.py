import os
import tempfile

# IMPORTANT: env vars must be set BEFORE importing app, since app reads them at module load.
_db_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"
os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

import pytest
from app import app as flask_app
from models import db


@pytest.fixture
def app():
    flask_app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with flask_app.app_context():
        db.drop_all()
        db.create_all()
    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


def pytest_unconfigure(config):
    try:
        os.close(_db_fd)
        os.unlink(_db_path)
    except Exception:
        pass
