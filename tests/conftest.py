import pytest
from fastapi.testclient import TestClient

from billbreaker import db
from billbreaker.config import settings
from billbreaker.main import create_app


@pytest.fixture(autouse=True)
def memory_db():
    db.use_database(":memory:")
    yield


@pytest.fixture
def set_setting():
    """Overrides a field on the frozen settings object for one test."""
    saved = {}

    def apply(name, value):
        saved.setdefault(name, getattr(settings, name))
        object.__setattr__(settings, name, value)

    yield apply
    for name, value in saved.items():
        object.__setattr__(settings, name, value)


@pytest.fixture
def client():
    return TestClient(create_app(), raise_server_exceptions=False)
