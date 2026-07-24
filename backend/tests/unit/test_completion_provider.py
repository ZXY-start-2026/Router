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


def model(*, disable_thinking: bool = False) -> ModelConfig:
    return ModelConfig(
        model_key="MODEL_A",
        display_name="A",
        router_model_name="a",
        endpoint_url="https://example.com/a/v1/completions",
        context_window=100,
        input_price_per_token=Decimal("0"),
        output_price_per_token=Decimal("0"),
        disable_thinking=disable_thinking,
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
        "stop": ["\nUser:", "\nSystem:"],
    }


def test_generated_user_turns_are_removed_from_completion(monkeypatch) -> None:
    response = Response()
    response.json = lambda: {
        **Response().json(),
        "choices": [
            {
                "text": (
                    "\nI am the assistant.\n\n"
                    "User:\nhello\n\nAssistant:\nHello again"
                ),
                "finish_reason": "length",
            }
        ],
    }
    monkeypatch.setattr(
        "app.providers.model.requests.post", lambda *args, **kwargs: response
    )
    provider = CompletionModelProvider((model(),), GenerationConfig())

    result = provider.generate(ModelRequest("prompt", "question", "MODEL_A"))

    assert result.content == "I am the assistant."


def test_thinking_is_disabled_in_prompt_and_removed_from_response(monkeypatch) -> None:
    captured = {}
    response = Response()
    response.json = lambda: {
        **Response().json(),
        "choices": [
            {
                "text": "<think>private reasoning</think>\n\nVisible answer",
                "finish_reason": "stop",
            }
        ],
    }

    def post(url, *, json, timeout):
        captured.update(json=json)
        return response

    monkeypatch.setattr("app.providers.model.requests.post", post)
    provider = CompletionModelProvider(
        (model(disable_thinking=True),),
        GenerationConfig(),
    )

    result = provider.generate(
        ModelRequest("User:\nhello\n\nAssistant:", "hello", "MODEL_A")
    )

    assert captured["json"]["prompt"] == (
        "User:\nhello\n/no_think\n\nAssistant:"
    )
    assert result.content == "Visible answer"


def test_memory_task_uses_gemma_turn_template(monkeypatch) -> None:
    captured = {}

    def post(url, *, json, timeout):
        captured.update(json=json)
        return Response()

    monkeypatch.setattr("app.providers.model.requests.post", post)
    provider = CompletionModelProvider((model(),), GenerationConfig())

    provider.generate(ModelRequest("memory body", "[MEMORY_TASK]", "MODEL_A"))

    assert captured["json"]["prompt"] == (
        "<start_of_turn>user\n"
        "memory body"
        "<end_of_turn>\n<start_of_turn>model\n"
    )


def test_memory_task_disables_thinking_for_supported_model(monkeypatch) -> None:
    captured = {}

    def post(url, *, json, timeout):
        captured.update(json=json)
        return Response()

    monkeypatch.setattr("app.providers.model.requests.post", post)
    provider = CompletionModelProvider(
        (model(disable_thinking=True),),
        GenerationConfig(),
    )

    provider.generate(ModelRequest("memory body", "[MEMORY_TASK]", "MODEL_A"))

    assert captured["json"]["prompt"] == (
        "User:\nmemory body\n/no_think\n\nAssistant:"
    )


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
