from __future__ import annotations

from decimal import Decimal

from app.core.config import ModelConfig, Settings
from app.providers.model import CompletionModelProvider, MockModelProvider, ModelProvider
from app.providers.router import LocalMirtRouterProvider, MockRouterProvider, RouterProvider
from app.providers.search import DisabledSearchProvider, MockSearchProvider, SearchProvider
from app.providers.tokenizer import LocalTokenizerProvider, MockTokenizerProvider, TokenizerProvider


def _mock_models() -> tuple[ModelConfig, ...]:
    return tuple(
        ModelConfig(
            model_key=key,
            display_name=f"{key}（Mock）",
            router_model_name=key,
            endpoint_url=f"mock://{key.lower()}",
            context_window=100_000,
            input_price_per_token=Decimal("0"),
            output_price_per_token=Decimal("0"),
            enabled=True,
        )
        for key in ("MODEL_A", "MODEL_B", "MODEL_C")
    )


class ProviderRegistry:
    def __init__(
        self,
        settings: Settings,
        *,
        model_override: ModelProvider | None = None,
        search_override: SearchProvider | None = None,
        router_override: RouterProvider | None = None,
        tokenizer_override: TokenizerProvider | None = None,
    ) -> None:
        use_mock_runtime = settings.mock_provider_enabled or model_override is not None
        self.models = settings.models if settings.models else _mock_models()
        if use_mock_runtime:
            self.model = model_override or MockModelProvider()
            self.search = search_override or MockSearchProvider()
            self.router = router_override or MockRouterProvider()
            self.tokenizer = tokenizer_override or MockTokenizerProvider()
            return
        self.model = CompletionModelProvider(self.models, settings.generation)
        self.search = search_override or DisabledSearchProvider()
        self.router = router_override or LocalMirtRouterProvider(
            settings.router, self.models
        )
        self.tokenizer = tokenizer_override or LocalTokenizerProvider()
