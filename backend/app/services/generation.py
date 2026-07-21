from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.config import ModelConfig, Settings
from app.core.enums import AttemptStatus, ErrorCategory, SelectionMode
from app.core.errors import ProviderError
from app.db.models_core import utc_now
from app.db.models_generation import GenerationTask
from app.providers.model import ModelProvider, ModelRequest, ModelResult
from app.repositories.generation import GenerationRepository
from app.services.routing import RoutePlan


@dataclass(frozen=True, slots=True)
class GenerationOutcome:
    result: ModelResult | None
    model: ModelConfig | None
    selection_mode: SelectionMode
    failure: ProviderError | None = None


class GenerationService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        models: tuple[ModelConfig, ...],
        provider: ModelProvider,
    ) -> None:
        self.session = session
        self.settings = settings
        self.models = {model.model_key: model for model in models}
        self.provider = provider
        self.repository = GenerationRepository(session)

    def execute_auto(
        self, task: GenerationTask, route_plan: RoutePlan, prompt: str, user_text: str
    ) -> GenerationOutcome:
        last_error: ProviderError | None = None
        for model_index, model_key in enumerate(route_plan.ordered_model_keys):
            model = self.models[model_key]
            retry_of: str | None = None
            for attempt_number in range(2):
                result, error, attempt_id = self._execute_once(
                    task, model, prompt, user_text, retry_of
                )
                if result is not None:
                    mode = (
                        SelectionMode.AUTO_ROUTE
                        if model_index == 0
                        else SelectionMode.AUTO_FALLBACK
                    )
                    return GenerationOutcome(result, model, mode)
                assert error is not None
                last_error = error
                if error.global_stop:
                    return GenerationOutcome(None, None, task.selection_mode, error)
                if attempt_number == 0 and error.retryable:
                    retry_of = attempt_id
                    continue
                break
            if last_error and not last_error.fallback_allowed:
                break
        return GenerationOutcome(None, None, task.selection_mode, last_error)

    def execute_manual(
        self, task: GenerationTask, model_key: str, prompt: str, user_text: str
    ) -> GenerationOutcome:
        model = self.models.get(model_key)
        if model is None or not model.enabled:
            error = ProviderError(
                "指定模型不可用",
                category=ErrorCategory.MODEL_UNAVAILABLE,
                provider_code="MODEL_DISABLED",
                fallback_allowed=False,
            )
            return GenerationOutcome(None, None, SelectionMode.USER_SELECTED, error)
        result, error, _ = self._execute_once(task, model, prompt, user_text, None)
        return GenerationOutcome(result, model if result else None, SelectionMode.USER_SELECTED, error)

    def _execute_once(
        self,
        task: GenerationTask,
        model: ModelConfig,
        prompt: str,
        user_text: str,
        retry_of_attempt_id: str | None,
    ) -> tuple[ModelResult | None, ProviderError | None, str]:
        started = utc_now()
        try:
            result = self.provider.generate(
                ModelRequest(
                    prompt=prompt,
                    current_user_text=user_text,
                    requested_model_key=model.model_key,
                )
            )
        except ProviderError as error:
            attempt = self.repository.append_attempt(
                generation_task_id=task.id,
                model_key=model.model_key,
                display_name_snapshot=model.display_name,
                response_model_snapshot=None,
                started_at=started,
                ended_at=utc_now(),
                status=AttemptStatus.FAILED,
                finish_reason=None,
                error_category=error.category,
                error_code=error.provider_code,
                error_message=error.message[:500],
                retry_of_attempt_id=retry_of_attempt_id,
                actual_input_tokens=None,
                actual_output_tokens=None,
                charged_cost=None,
                price_version=self.settings.price_version,
                provider_request_id=None,
            )
            self.session.commit()
            return None, error, attempt.id
        except Exception as exc:
            error = ProviderError(
                "模型调用发生未知错误",
                category=ErrorCategory.UNKNOWN,
                provider_code=type(exc).__name__,
            )
            attempt = self.repository.append_attempt(
                generation_task_id=task.id,
                model_key=model.model_key,
                display_name_snapshot=model.display_name,
                response_model_snapshot=None,
                started_at=started,
                ended_at=utc_now(),
                status=AttemptStatus.FAILED,
                finish_reason=None,
                error_category=error.category,
                error_code=error.provider_code,
                error_message=error.message,
                retry_of_attempt_id=retry_of_attempt_id,
                actual_input_tokens=None,
                actual_output_tokens=None,
                charged_cost=None,
                price_version=self.settings.price_version,
                provider_request_id=None,
            )
            self.session.commit()
            return None, error, attempt.id

        cost = self.actual_cost(model, result.input_tokens, result.output_tokens)
        attempt = self.repository.append_attempt(
            generation_task_id=task.id,
            model_key=model.model_key,
            display_name_snapshot=model.display_name,
            response_model_snapshot=result.model_id,
            started_at=started,
            ended_at=utc_now(),
            status=AttemptStatus.SUCCEEDED,
            finish_reason=result.finish_reason,
            error_category=None,
            error_code=None,
            error_message=None,
            retry_of_attempt_id=retry_of_attempt_id,
            actual_input_tokens=result.input_tokens,
            actual_output_tokens=result.output_tokens,
            charged_cost=cost,
            price_version=self.settings.price_version,
            provider_request_id=result.provider_request_id,
        )
        self.session.commit()
        return result, None, attempt.id

    @staticmethod
    def actual_cost(model: ModelConfig, input_tokens: int, output_tokens: int) -> Decimal:
        return (
            Decimal(input_tokens) * model.input_price_per_token
            + Decimal(output_tokens) * model.output_price_per_token
        )
