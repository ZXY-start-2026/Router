from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass

import requests

from app.core.config import GenerationConfig, ModelConfig
from app.core.enums import ErrorCategory
from app.core.errors import ProviderError


COMPLETION_STOP_SEQUENCES = ("\nUser:", "\nSystem:")
_THINK_BLOCK_PATTERN = re.compile(
    r"<think(?:\s[^>]*)?>.*?</think\s*>",
    re.IGNORECASE | re.DOTALL,
)
_THINK_OPEN_PATTERN = re.compile(
    r"<think(?:\s[^>]*)?>",
    re.IGNORECASE,
)
_GENERATED_TURN_PATTERN = re.compile(
    r"(?im)^[ \t]*(?:user|system)[ \t]*:"
)


def sanitize_completion_text(content: str) -> str:
    """Keep only the visible answer for storage and future prompt history."""
    content = _THINK_BLOCK_PATTERN.sub("", content)
    incomplete_thinking = _THINK_OPEN_PATTERN.search(content)
    if incomplete_thinking is not None:
        content = content[: incomplete_thinking.start()]
    boundary = _GENERATED_TURN_PATTERN.search(content)
    if boundary is not None:
        content = content[: boundary.start()]
    return content.strip()


def prompt_for_model(request: ModelRequest, model: ModelConfig) -> str:
    if not model.disable_thinking:
        return request.prompt
    assistant_suffix = "\n\nAssistant:"
    if request.prompt.endswith(assistant_suffix):
        return (
            request.prompt[: -len(assistant_suffix)]
            + "\n/no_think"
            + assistant_suffix
        )
    return request.prompt + "\n/no_think"


@dataclass(frozen=True, slots=True)
class ModelRequest:
    prompt: str
    current_user_text: str
    requested_model_key: str


@dataclass(frozen=True, slots=True)
class ModelResult:
    content: str
    model_key: str
    model_id: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    finish_reason: str
    provider_request_id: str


@dataclass(frozen=True, slots=True)
class ModelOption:
    model_key: str
    label: str
    available: bool


class ModelProvider(ABC):
    @abstractmethod
    def generate(self, request: ModelRequest) -> ModelResult:
        raise NotImplementedError

    @abstractmethod
    def model_options(self) -> tuple[ModelOption, ...]:
        raise NotImplementedError


class CompletionModelProvider(ModelProvider):
    def __init__(
        self,
        models: tuple[ModelConfig, ...],
        generation: GenerationConfig,
    ) -> None:
        self.models = {model.model_key: model for model in models}
        self.generation = generation

    def generate(self, request: ModelRequest) -> ModelResult:
        model = self.models.get(request.requested_model_key)
        if model is None or not model.enabled or model.endpoint_url is None:
            raise ProviderError(
                "模型未启用或接口未配置",
                category=ErrorCategory.MODEL_UNAVAILABLE,
                provider_code="MODEL_DISABLED",
            )
        payload = {
            "prompt": prompt_for_model(request, model),
            "max_tokens": self.generation.max_tokens,
            "temperature": float(self.generation.temperature),
            "stop": list(COMPLETION_STOP_SEQUENCES),
        }
        try:
            response = requests.post(
                model.endpoint_url,
                json=payload,
                timeout=model.request_timeout_seconds,
            )
        except requests.Timeout as exc:
            raise ProviderError(
                "模型请求超时",
                category=ErrorCategory.TRANSIENT_TIMEOUT,
                provider_code="TIMEOUT",
                retryable=True,
            ) from exc
        except requests.ConnectionError as exc:
            raise ProviderError(
                "模型网络连接失败",
                category=ErrorCategory.TRANSIENT_NETWORK,
                provider_code="CONNECTION_ERROR",
                retryable=True,
            ) from exc
        except requests.RequestException as exc:
            raise ProviderError(
                "模型请求失败",
                category=ErrorCategory.UNKNOWN,
                provider_code="REQUEST_ERROR",
            ) from exc

        if response.status_code == 429:
            raise ProviderError(
                "模型服务限流",
                category=ErrorCategory.TRANSIENT_RATE_LIMIT,
                provider_code="HTTP_429",
                retryable=True,
            )
        if response.status_code >= 500:
            raise ProviderError(
                "模型服务暂时不可用",
                category=ErrorCategory.TRANSIENT_SERVER,
                provider_code=f"HTTP_{response.status_code}",
                retryable=True,
            )
        if not response.ok:
            raise ProviderError(
                "模型拒绝了本次请求",
                category=ErrorCategory.MODEL_REQUEST_REJECTED,
                provider_code=f"HTTP_{response.status_code}",
            )
        try:
            payload_json = response.json()
        except ValueError as exc:
            raise self._invalid_response("模型返回的不是有效 JSON", exc)
        return self._parse_response(request.requested_model_key, payload_json)

    @staticmethod
    def _invalid_response(message: str, cause: Exception | None = None) -> ProviderError:
        error = ProviderError(
            message,
            category=ErrorCategory.MODEL_RESPONSE_INVALID,
            provider_code="INVALID_RESPONSE",
        )
        if cause is not None:
            error.__cause__ = cause
        return error

    @classmethod
    def _parse_response(cls, model_key: str, payload: object) -> ModelResult:
        try:
            if not isinstance(payload, dict) or payload.get("object") != "text_completion":
                raise ValueError("object")
            request_id = cls._non_empty_string(payload.get("id"), "id")
            response_model = cls._non_empty_string(payload.get("model"), "model")
            choices = payload.get("choices")
            if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
                raise ValueError("choices")
            content = choices[0].get("text")
            if not isinstance(content, str) or not content.strip():
                raise ValueError("choices[0].text")
            content = sanitize_completion_text(content)
            if not content:
                raise ValueError("choices[0].text")
            finish_reason = cls._non_empty_string(
                choices[0].get("finish_reason"), "finish_reason"
            )
            usage = payload.get("usage")
            if not isinstance(usage, dict):
                raise ValueError("usage")
            input_tokens = cls._token_count(usage.get("prompt_tokens"), "prompt_tokens")
            output_tokens = cls._token_count(
                usage.get("completion_tokens"), "completion_tokens"
            )
            total_tokens = cls._token_count(usage.get("total_tokens"), "total_tokens")
            if total_tokens != input_tokens + output_tokens:
                raise ValueError("total_tokens")
        except (KeyError, TypeError, ValueError) as exc:
            raise cls._invalid_response("模型响应字段不完整或类型错误", exc)
        return ModelResult(
            content=content,
            model_key=model_key,
            model_id=response_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            finish_reason=finish_reason,
            provider_request_id=request_id,
        )

    @staticmethod
    def _non_empty_string(value: object, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(field_name)
        return value

    @staticmethod
    def _token_count(value: object, field_name: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(field_name)
        return value

    def model_options(self) -> tuple[ModelOption, ...]:
        return tuple(
            ModelOption(model.model_key, model.display_name, model.enabled)
            for model in self.models.values()
        )


class MockModelProvider(ModelProvider):
    """Explicit development/test provider; never registered in production."""

    def __init__(
        self,
        responder: Callable[[ModelRequest], ModelResult] | None = None,
    ) -> None:
        self._responder = responder or self._default_response

    def generate(self, request: ModelRequest) -> ModelResult:
        return self._responder(request)

    def model_options(self) -> tuple[ModelOption, ...]:
        return tuple(
            ModelOption(key, f"{key}（Mock）", True)
            for key in ("MODEL_A", "MODEL_B", "MODEL_C")
        )

    @staticmethod
    def _default_response(request: ModelRequest) -> ModelResult:
        content = f"Mock 回复：{request.current_user_text}"
        input_tokens = max(1, len(request.prompt.encode("utf-8")) // 3)
        output_tokens = max(1, len(content.encode("utf-8")) // 3)
        return ModelResult(
            content=content,
            model_key=request.requested_model_key,
            model_id=f"mock-{request.requested_model_key.lower()}",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            finish_reason="stop",
            provider_request_id="mock-request",
        )


class UnavailableModelProvider(ModelProvider):
    def generate(self, request: ModelRequest) -> ModelResult:
        raise ProviderError(
            "尚未配置真实模型 Provider",
            category=ErrorCategory.MODEL_UNAVAILABLE,
            provider_code="UNAVAILABLE",
        )

    def model_options(self) -> tuple[ModelOption, ...]:
        return tuple(
            ModelOption(key, key, False) for key in ("MODEL_A", "MODEL_B", "MODEL_C")
        )
