import pytest

from app.core.config import Settings


def test_mock_provider_is_forbidden_in_production() -> None:
    settings = Settings(environment="production", mock_provider_enabled=True)
    with pytest.raises(ValueError, match="Mock provider"):
        settings.validate_runtime()

