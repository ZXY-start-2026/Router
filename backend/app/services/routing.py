from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from time import perf_counter

from sqlalchemy.orm import Session

from app.core.config import ModelConfig, Settings
from app.core.errors import ConflictError
from app.db.models_generation import GenerationTask, RouteSnapshot
from app.providers.router import RouterCandidateInput, RouterProvider, RouterRequest
from app.providers.tokenizer import TokenizerProvider
from app.repositories.generation import GenerationRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RoutePlan:
    snapshot: RouteSnapshot
    ordered_model_keys: tuple[str, ...]


class RoutingService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        models: tuple[ModelConfig, ...],
        router: RouterProvider,
        tokenizer: TokenizerProvider,
    ) -> None:
        self.settings = settings
        self.models = models
        self.router = router
        self.tokenizer = tokenizer
        self.repository = GenerationRepository(session)

    def route(self, task: GenerationTask, question: str, prompt: str) -> RoutePlan:
        started = perf_counter()
        rows: list[dict[str, object]] = []
        eligible_models: list[ModelConfig] = []
        for model in self.models:
            base = {
                "model_key": model.model_key,
                "display_name_snapshot": model.display_name,
                "router_model_name_snapshot": model.router_model_name,
            }
            if not model.enabled:
                rows.append({**base, "eligible": False, "ineligible_reason": "MODEL_DISABLED"})
                continue
            try:
                input_tokens = self.tokenizer.count_prompt(model, prompt)
            except Exception:
                rows.append({**base, "eligible": False, "ineligible_reason": "TOKENIZER_UNAVAILABLE"})
                continue
            if model.context_window is None or input_tokens + model.estimated_output_tokens > model.context_window:
                rows.append({**base, "eligible": False, "ineligible_reason": "CONTEXT_LIMIT_EXCEEDED"})
                continue
            predicted_cost = (
                Decimal(input_tokens) * model.input_price_per_token
                + Decimal(model.estimated_output_tokens) * model.output_price_per_token
            )
            rows.append(
                {
                    **base,
                    "eligible": True,
                    "ineligible_reason": None,
                    "predicted_input_tokens": input_tokens,
                    "predicted_output_tokens": model.estimated_output_tokens,
                    "predicted_cost": predicted_cost,
                }
            )
            eligible_models.append(model)
        if not eligible_models:
            raise ConflictError("没有可参与路由的模型")

        prediction_set = self.router.predict(
            RouterRequest(
                question=question,
                candidates=tuple(
                    RouterCandidateInput(model.model_key, model.router_model_name)
                    for model in eligible_models
                ),
            )
        )
        scored = [row for row in rows if row["eligible"]]
        positive_costs = [
            row["predicted_cost"] for row in scored if row["predicted_cost"] > 0
        ]
        minimum_positive = min(positive_costs) if positive_costs else None
        for row in scored:
            cost = row["predicted_cost"]
            if cost == 0 or minimum_positive is None:
                cost_score = Decimal("1")
            else:
                cost_score = minimum_positive / cost
            accuracy = Decimal(str(prediction_set.predictions[str(row["model_key"])]))
            row["predicted_accuracy"] = accuracy
            row["cost_score"] = cost_score
            row["route_score"] = (
                self.settings.accuracy_weight * accuracy
                + self.settings.cost_weight * cost_score
            )
        scored.sort(
            key=lambda row: (
                -row["route_score"],
                -row["predicted_accuracy"],
                row["predicted_cost"],
                row["model_key"],
            )
        )
        for rank, row in enumerate(scored, start=1):
            row["rank"] = rank

        snapshot = self.repository.create_route_snapshot(
            task,
            metadata={
                "strategy_version": self.settings.router.strategy_version,
                "router_provider_version": prediction_set.version,
                "accuracy_weight": self.settings.accuracy_weight,
                "cost_weight": self.settings.cost_weight,
                "price_version": self.settings.price_version,
                "model_config_snapshot_json": [model.safe_snapshot() for model in self.models],
                "routing_latency_ms": int((perf_counter() - started) * 1000),
            },
            candidates=rows,
        )
        ranked = [
            (row["model_key"], row["rank"], round(float(row["route_score"]), 4),
             round(float(row["predicted_accuracy"]), 4), round(float(row["cost_score"]), 4))
            for row in scored
        ]
        ineligible = [r["model_key"] for r in rows if not r["eligible"]]
        logger.info(
            "route task=%s ranks=%s ineligible=%s latency=%dms",
            task.id, ranked, ineligible, int((perf_counter() - started) * 1000),
        )
        return RoutePlan(
            snapshot=snapshot,
            ordered_model_keys=tuple(str(row["model_key"]) for row in scored),
        )
