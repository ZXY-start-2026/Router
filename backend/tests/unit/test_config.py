import pytest

from app.core.config import GenerationConfig, Settings


def test_mock_provider_is_forbidden_in_production() -> None:
    settings = Settings(environment="production", mock_provider_enabled=True)
    with pytest.raises(ValueError, match="Mock provider"):
        settings.validate_runtime()


def test_generation_max_tokens_is_configurable() -> None:
    settings = Settings(
        environment="test",
        mock_provider_enabled=True,
        generation=GenerationConfig(max_tokens=2048),
    )
    settings.validate_runtime()


def test_generation_max_tokens_must_be_positive() -> None:
    settings = Settings(
        environment="test",
        mock_provider_enabled=True,
        generation=GenerationConfig(max_tokens=0),
    )
    with pytest.raises(ValueError, match="max_tokens"):
        settings.validate_runtime()
