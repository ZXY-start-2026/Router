from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db import models_core
from app.db.session import Base
from app.main import create_app
from app.providers.model import MockModelProvider


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        environment="test",
        database_url="sqlite://",
        mock_provider_enabled=True,
    )


@pytest.fixture
def app(test_settings: Settings):
    application = create_app(test_settings, MockModelProvider())
    Base.metadata.create_all(application.state.engine)
    yield application
    application.state.engine.dispose()


@pytest.fixture
def client(app) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
