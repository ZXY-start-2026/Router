from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.config import ModelConfig, Settings
from app.core.enums import (
    AttemptStatus,
    ErrorCategory,
    GenerationMode,
    GenerationStatus,
    SearchStatus,
    SelectionMode,
)
from app.core.errors import AppError, ProviderError
from app.db.models_core import AssistantAnswerVersion, Branch, UserMessage, utc_now
from app.db.models_generation import GenerationTask, SearchSnapshot
from app.providers.model import ModelProvider, ModelRequest, ModelResult
from app.providers.registry import ProviderRegistry
from app.providers.search import SearchRequest, SearchResponse
from app.repositories.chat import ChatRepository
from app.repositories.generation import GenerationRepository
from app.services.context import ContextService
from app.services.routing import RoutePlan
from app.services.routing import RoutingService

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class GenerationOutcome:
    result: ModelResult | None
    model: ModelConfig | None
    selection_mode: SelectionMode
    failure: ProviderError | None = None


@dataclass(frozen=True, slots=True)
class GenerationRunResult:
    task: GenerationTask | None
    answer: AssistantAnswerVersion
    status: GenerationStatus
    search_status: SearchStatus
    selected_model_key: str | None = None
    finish_reason: str | None = None
    failure_code: str | None = None
    failure_message: str | None = None


class GenerationService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        models: tuple[ModelConfig, ...],
        provider: ModelProvider,
        providers: ProviderRegistry | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.models = {model.model_key: model for model in models}
        self.provider = provider
        self.providers = providers
        self.repository = GenerationRepository(session)
        self.chat = ChatRepository(session)

    def create_search_snapshot(self, message: UserMessage) -> SearchSnapshot:
        if self.providers is None:
            raise RuntimeError("搜索需要完整 ProviderRegistry")
        try:
            response = self.providers.search.search(
                SearchRequest(
                    query=message.content,
                    max_results=self.settings.search_max_results,
                )
            )
        except Exception:
            response = SearchResponse(
                provider="360",
                status=SearchStatus.FAILED,
                query=message.content,
                failure_code="SEARCH_PROVIDER_ERROR",
                failure_message="联网搜索失败，本轮继续使用模型自身知识回答。",
            )
        snapshot = self.repository.create_search_snapshot(message, response)
        self.session.commit()
        return snapshot

    def run(
        self,
        *,
        branch: Branch,
        message: UserMessage,
        search_snapshot: SearchSnapshot,
        selection_mode: SelectionMode,
        requested_model_key: str | None,
        generation_mode: GenerationMode,
        source_answer_version_id: str | None = None,
    ) -> GenerationRunResult:
        if self.providers is None:
            raise RuntimeError("生成编排需要完整 ProviderRegistry")
        answer = self.chat.create_answer_version(message.id, selection_mode)
        task: GenerationTask | None = None
        try:
            prepared = ContextService(self.session, self.settings).prepare(
                branch_id=branch.id,
                message=message,
                search_snapshot=search_snapshot,
            )
            task = self.repository.create_task(
                user_message_id=message.id,
                branch_id=branch.id,
                selection_mode=selection_mode,
                requested_model_key=requested_model_key,
                search_snapshot_id=search_snapshot.id,
                context_snapshot_id=prepared.snapshot.id,
                generation_mode=generation_mode,
                source_answer_version_id=source_answer_version_id,
            )
            self.repository.bind_answer_to_task(answer, task)
            self.session.commit()

            route_plan = None
            if selection_mode == SelectionMode.AUTO_ROUTE:
                route_plan = RoutingService(
                    self.session,
                    self.settings,
                    self.providers.models,
                    self.providers.router,
                    self.providers.tokenizer,
                ).route(task, message.content, prepared.prompt)
                answer.route_snapshot_id = route_plan.snapshot.id
                self.session.commit()
                outcome = self.execute_auto(
                    task, route_plan, prepared.prompt, message.content
                )
            else:
                assert requested_model_key is not None
                outcome = self.execute_manual(
                    task, requested_model_key, prepared.prompt, message.content
                )

            if outcome.result is None or outcome.model is None:
                error = outcome.failure or ProviderError("所有候选模型均生成失败")
                return self._finish_failure(
                    message,
                    answer,
                    task,
                    search_snapshot.status,
                    error.category,
                    error.provider_code or error.code,
                    error.message,
                )

            candidate = (
                self.repository.get_candidate(
                    route_plan.snapshot.id, outcome.model.model_key
                )
                if route_plan is not None
                else None
            )
            actual_cost = self.actual_cost(
                outcome.model,
                outcome.result.input_tokens,
                outcome.result.output_tokens,
            )
            self.chat.complete_answer(
                message,
                answer,
                content=outcome.result.content,
                model_key=outcome.result.model_key,
                model_id=outcome.result.model_id,
                display_name=outcome.model.display_name,
                selection_mode=outcome.selection_mode,
                route_snapshot_id=route_plan.snapshot.id if route_plan else None,
                predicted_input_tokens=(
                    candidate.predicted_input_tokens if candidate else None
                ),
                predicted_output_tokens=(
                    candidate.predicted_output_tokens if candidate else None
                ),
                predicted_cost=(candidate.predicted_cost if candidate else None),
                actual_input_tokens=outcome.result.input_tokens,
                actual_output_tokens=outcome.result.output_tokens,
                actual_cost=actual_cost,
                price_version=self.settings.price_version,
            )
            self.repository.succeed_task(task)
            self.session.commit()
            return GenerationRunResult(
                task=task,
                answer=answer,
                status=GenerationStatus.SUCCEEDED,
                search_status=search_snapshot.status,
                selected_model_key=outcome.result.model_key,
                finish_reason=outcome.result.finish_reason,
            )
        except AppError as error:
            category = (
                error.category
                if isinstance(error, ProviderError)
                else ErrorCategory.UNKNOWN
            )
            return self._finish_failure(
                message,
                answer,
                task,
                search_snapshot.status,
                category,
                error.code,
                error.message,
            )
        except Exception:
            return self._finish_failure(
                message,
                answer,
                task,
                search_snapshot.status,
                ErrorCategory.UNKNOWN,
                "GENERATION_PIPELINE_ERROR",
                "生成流程失败",
            )

    def _finish_failure(
        self,
        message: UserMessage,
        answer: AssistantAnswerVersion,
        task: GenerationTask | None,
        search_status: SearchStatus,
        category: ErrorCategory,
        code: str,
        message_text: str,
    ) -> GenerationRunResult:
        if task is not None:
            self.repository.fail_task(task, category, message_text)
        self.chat.mark_answer_failed(message, answer)
        self.session.commit()
        return GenerationRunResult(
            task=task,
            answer=answer,
            status=GenerationStatus.FAILED,
            search_status=search_status,
            failure_code=code,
            failure_message=message_text,
        )

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
                    logger.info(
                        "attempt task=%s model=%s rank=%d attempt=%d mode=%s result=OK tokens=(%d,%d)",
                        task.id, model_key, model_index + 1, attempt_number + 1,
                        mode, result.input_tokens, result.output_tokens,
                    )
                    return GenerationOutcome(result, model, mode)
                assert error is not None
                last_error = error
                logger.warning(
                    "attempt task=%s model=%s rank=%d attempt=%d mode=FAIL category=%s code=%s retryable=%s",
                    task.id, model_key, model_index + 1, attempt_number + 1,
                    error.category, error.provider_code, error.retryable,
                )
                if error.global_stop:
                    return GenerationOutcome(None, None, task.selection_mode, error)
                if attempt_number == 0 and error.retryable:
                    retry_of = attempt_id
                    continue
                break
            if last_error and not last_error.fallback_allowed:
                break
        logger.error(
            "task=%s exhausted models=%s",
            task.id, list(route_plan.ordered_model_keys),
        )
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
