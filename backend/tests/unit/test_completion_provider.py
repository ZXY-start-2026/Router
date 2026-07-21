from decimal import Decimal

import pytest

from app.core.config import GenerationConfig, ModelConfig
from app.core.enums import ErrorCategory
from app.core.errors import ProviderError
from app.providers.model import CompletionModelProvider, ModelRequest


class Response:
    status_code = 200
    ok = True

    def json(self):
        return {
            "id": "request-1",
            "object": "text_completion",
            "model": "provider/model",
            "choices": [{"text": "2", "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6},
        }


def model() -> ModelConfig:
    return ModelConfig(
        model_key="MODEL_A",
        display_name="A",
        router_model_name="a",
        endpoint_url="https://example.com/a/v1/completions",
        context_window=100,
        input_price_per_token=Decimal("0"),
        output_price_per_token=Decimal("0"),
    )


def test_completion_request_has_only_confirmed_fields(monkeypatch) -> None:
    captured = {}

    def post(url, *, json, timeout):
        captured.update(url=url, json=json, timeout=timeout)
        return Response()

    monkeypatch.setattr("app.providers.model.requests.post", post)
    provider = CompletionModelProvider((model(),), GenerationConfig())
    result = provider.generate(ModelRequest("prompt", "question", "MODEL_A"))
    assert result.content == "2"
    assert captured["json"] == {
        "prompt": "prompt",
        "max_tokens": 1024,
        "temperature": 0.7,
    }


def test_invalid_usage_is_rejected(monkeypatch) -> None:
    response = Response()
    response.json = lambda: {
        **Response().json(),
        "usage": {"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 7},
    }
    monkeypatch.setattr("app.providers.model.requests.post", lambda *args, **kwargs: response)
    provider = CompletionModelProvider((model(),), GenerationConfig())
    with pytest.raises(ProviderError) as raised:
        provider.generate(ModelRequest("prompt", "question", "MODEL_A"))
    assert raised.value.category == ErrorCategory.MODEL_RESPONSE_INVALID
