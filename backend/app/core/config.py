from __future__ import annotations

import os
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlparse

import yaml


BACKEND_ROOT = Path(__file__).resolve().parents[2]
MODEL_KEYS = ("MODEL_A", "MODEL_B", "MODEL_C")


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _resolve_path(value: str | Path, base: Path = BACKEND_ROOT) -> Path:
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (base / path).resolve()


def _decimal(value: object, field_name: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field_name} must be a decimal") from exc
    if not result.is_finite() or result < 0:
        raise ValueError(f"{field_name} must be a non-negative finite decimal")
    return result


@dataclass(frozen=True, slots=True)
class GenerationConfig:
    max_tokens: int = 1024
    temperature: Decimal = Decimal("0.7")
    logprobs: None = None
    logprobs_mode: None = None


@dataclass(frozen=True, slots=True)
class RouterConfig:
    asset_dir: Path = Path("resources/router")
    device: str = "cpu"
    lambda_value: Decimal = Decimal("0.1")
    knowledge_n: int = 25
    knn_neighbors: int = 5
    strategy_version: str = "mirt-bert-cost-v1"


@dataclass(frozen=True, slots=True)
class ModelConfig:
    model_key: str
    display_name: str
    router_model_name: str
    endpoint_url: str | None
    context_window: int | None
    input_price_per_token: Decimal
    output_price_per_token: Decimal
    estimated_output_tokens: int = 512
    request_timeout_seconds: float = 120.0
    tokenizer_path: Path | None = None
    disable_thinking: bool = False
    enabled: bool = True

    def safe_snapshot(self) -> dict[str, object]:
        return {
            "model_key": self.model_key,
            "display_name": self.display_name,
            "router_model_name": self.router_model_name,
            "context_window": self.context_window,
            "input_price_per_token": str(self.input_price_per_token),
            "output_price_per_token": str(self.output_price_per_token),
            "estimated_output_tokens": self.estimated_output_tokens,
            "disable_thinking": self.disable_thinking,
            "enabled": self.enabled,
        }


@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str = "Multi Model Chat"
    environment: str = "development"
    database_url: str = "sqlite:///./data/chat.db"
    cors_origins: tuple[str, ...] = ("http://localhost:5173",)
    conversation_page_size: int = 20
    conversation_page_max_size: int = 100
    title_max_chars: int = 30
    mock_provider_enabled: bool = False
    search_max_results: int = 5
    system_rules_text: str = ""
    accuracy_weight: Decimal = Decimal("0.70")
    cost_weight: Decimal = Decimal("0.30")
    price_version: str = "2026-07-user-confirmed-v1"
    generation: GenerationConfig = field(default_factory=GenerationConfig)
    router: RouterConfig = field(default_factory=RouterConfig)
    models: tuple[ModelConfig, ...] = ()

    @classmethod
    def load(cls) -> "Settings":
        environment = os.getenv("APP_ENV", "development").lower()
        mock_default = environment == "development"
        config_path = _resolve_path(
            os.getenv("MODELS_CONFIG_PATH", "config/models.yaml")
        )
        document: dict[str, object] = {}
        if config_path.exists():
            loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            if loaded is not None and not isinstance(loaded, dict):
                raise ValueError("models.yaml root must be a mapping")
            document = loaded or {}

        generation_data = document.get("generation", {})
        if not isinstance(generation_data, dict):
            raise ValueError("generation config must be a mapping")
        generation = GenerationConfig(
            max_tokens=int(generation_data.get("max_tokens", 1024)),
            temperature=_decimal(generation_data.get("temperature", "0.7"), "temperature"),
            logprobs=generation_data.get("logprobs"),
            logprobs_mode=generation_data.get("logprobs_mode"),
        )

        models_data = document.get("models", {})
        if not isinstance(models_data, dict):
            raise ValueError("models config must be a mapping")
        models = tuple(
            cls._parse_model(key, models_data[key])
            for key in MODEL_KEYS
            if key in models_data
        )

        origins = tuple(
            value.strip()
            for value in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
            if value.strip()
        )
        settings = cls(
            app_name=os.getenv("APP_NAME", "Multi Model Chat"),
            environment=environment,
            database_url=os.getenv("DATABASE_URL", "sqlite:///./data/chat.db"),
            cors_origins=origins,
            conversation_page_size=int(os.getenv("CONVERSATION_PAGE_SIZE", "20")),
            conversation_page_max_size=int(os.getenv("CONVERSATION_PAGE_MAX_SIZE", "100")),
            title_max_chars=int(os.getenv("TITLE_MAX_CHARS", "30")),
            mock_provider_enabled=_as_bool(
                os.getenv("MOCK_PROVIDER_ENABLED"), mock_default
            ),
            system_rules_text=os.getenv("SYSTEM_RULES_TEXT", ""),
            accuracy_weight=_decimal(
                os.getenv("ROUTER_ACCURACY_WEIGHT", "0.70"), "accuracy_weight"
            ),
            cost_weight=_decimal(
                os.getenv("ROUTER_COST_WEIGHT", "0.30"), "cost_weight"
            ),
            price_version=os.getenv(
                "MODEL_PRICE_VERSION", "2026-07-user-confirmed-v1"
            ),
            generation=generation,
            router=RouterConfig(
                asset_dir=_resolve_path(
                    os.getenv("ROUTER_ASSET_DIR", "resources/router")
                )
            ),
            models=models,
        )
        settings.validate_runtime()
        return settings

    @staticmethod
    def _parse_model(model_key: str, raw: object) -> ModelConfig:
        if not isinstance(raw, dict):
            raise ValueError(f"{model_key} must be a mapping")
        tokenizer_value = raw.get("tokenizer_path")
        endpoint = str(raw.get("endpoint_url") or "").strip() or None
        context = raw.get("context_window")
        return ModelConfig(
            model_key=model_key,
            display_name=str(raw.get("display_name") or "").strip(),
            router_model_name=str(raw.get("router_model_name") or "").strip(),
            endpoint_url=endpoint,
            context_window=int(context) if context is not None else None,
            input_price_per_token=_decimal(
                raw.get("input_price_per_token", 0),
                f"{model_key}.input_price_per_token",
            ),
            output_price_per_token=_decimal(
                raw.get("output_price_per_token", 0),
                f"{model_key}.output_price_per_token",
            ),
            estimated_output_tokens=int(raw.get("estimated_output_tokens", 512)),
            request_timeout_seconds=float(raw.get("request_timeout_seconds", 120)),
            tokenizer_path=(
                _resolve_path(str(tokenizer_value)) if tokenizer_value else None
            ),
            disable_thinking=_as_bool(str(raw.get("disable_thinking", False))),
            enabled=_as_bool(str(raw.get("enabled", True)), True),
        )

    def model(self, model_key: str) -> ModelConfig | None:
        return next((model for model in self.models if model.model_key == model_key), None)

    def validate_runtime(self) -> None:
        if self.environment not in {"development", "test", "production"}:
            raise ValueError("APP_ENV must be development, test, or production")
        if self.environment == "production" and self.mock_provider_enabled:
            raise ValueError("Mock provider cannot be enabled in production")
        if not 1 <= self.conversation_page_size <= self.conversation_page_max_size:
            raise ValueError("Invalid conversation page size")
        if self.conversation_page_max_size > 100:
            raise ValueError("Conversation page maximum cannot exceed 100")
        if self.title_max_chars <= 0:
            raise ValueError("TITLE_MAX_CHARS must be positive")
        if self.accuracy_weight + self.cost_weight != Decimal("1"):
            raise ValueError("Router weights must sum to 1")
        if self.generation.max_tokens <= 0:
            raise ValueError("generation.max_tokens must be positive")
        if self.generation.temperature != Decimal("0.7"):
            raise ValueError("generation.temperature must be 0.7")
        if self.generation.logprobs is not None or self.generation.logprobs_mode is not None:
            raise ValueError("logprobs and logprobs_mode must be null")
        if self.mock_provider_enabled:
            return
        if tuple(model.model_key for model in self.models) != MODEL_KEYS:
            raise ValueError("models.yaml must contain MODEL_A, MODEL_B, and MODEL_C")
        router_names: set[str] = set()
        for model in self.models:
            if not model.display_name or not model.router_model_name:
                raise ValueError(f"{model.model_key} names cannot be empty")
            if model.router_model_name in router_names:
                raise ValueError("router_model_name values must be unique")
            router_names.add(model.router_model_name)
            if not 0 < model.estimated_output_tokens <= self.generation.max_tokens:
                raise ValueError(f"Invalid estimated_output_tokens for {model.model_key}")
            if model.request_timeout_seconds <= 0:
                raise ValueError(f"Invalid timeout for {model.model_key}")
            if not model.enabled:
                continue
            if model.context_window is None or model.context_window <= 0:
                raise ValueError(f"Invalid context_window for {model.model_key}")
            if model.endpoint_url is None:
                raise ValueError(f"Missing endpoint_url for {model.model_key}")
            parsed = urlparse(model.endpoint_url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError(f"Invalid endpoint_url for {model.model_key}")
            if not parsed.path.endswith("/v1/completions"):
                raise ValueError(f"endpoint_url must end with /v1/completions for {model.model_key}")
            if model.tokenizer_path is None:
                raise ValueError(f"Missing tokenizer_path for {model.model_key}")
        if not self.router.asset_dir.exists():
            raise ValueError(f"Router asset directory does not exist: {self.router.asset_dir}")
