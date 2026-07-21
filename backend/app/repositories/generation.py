from __future__ import annotations

import hashlib
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import GenerationMode, GenerationStatus, SelectionMode
from app.db.models_core import AssistantAnswerVersion, UserMessage, utc_now
from app.db.models_generation import (
    ContextSnapshot,
    GenerationAttempt,
    GenerationTask,
    RouteCandidate,
    RouteSnapshot,
    SearchResult,
    SearchSnapshot,
)
from app.providers.search import SearchResponse


@dataclass(frozen=True, slots=True)
class GenerationDetails:
    task: GenerationTask
    search: SearchSnapshot
    route: RouteSnapshot | None
    candidates: list[RouteCandidate]
    attempts: list[GenerationAttempt]


class GenerationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_search_snapshot(
        self, message: UserMessage, response: SearchResponse
    ) -> SearchSnapshot:
        snapshot = SearchSnapshot(
            user_message_id=message.id,
            query=response.query,
            provider=response.provider,
            status=response.status,
            failure_code=response.failure_code,
            failure_message=response.failure_message,
            latency_ms=response.latency_ms,
            provider_metadata_json={},
        )
        self.session.add(snapshot)
        self.session.flush()
        for rank, item in enumerate(response.results, start=1):
            key_source = f"{item.url}\n{item.title}\n{item.snippet}"
            self.session.add(
                SearchResult(
                    search_snapshot_id=snapshot.id,
                    rank=rank,
                    title=item.title,
                    snippet=item.snippet,
                    url=item.url,
                    dedupe_key=hashlib.sha256(key_source.encode("utf-8")).hexdigest(),
                )
            )
        message.search_snapshot_id = snapshot.id
        return snapshot

    def create_context_snapshot(self, **values) -> ContextSnapshot:
        snapshot = ContextSnapshot(**values)
        self.session.add(snapshot)
        self.session.flush()
        return snapshot

    def create_task(
        self,
        *,
        user_message_id: str,
        branch_id: str,
        selection_mode: SelectionMode,
        requested_model_key: str | None,
        search_snapshot_id: str,
        context_snapshot_id: str,
    ) -> GenerationTask:
        task = GenerationTask(
            user_message_id=user_message_id,
            branch_id=branch_id,
            generation_mode=GenerationMode.NEW_MESSAGE,
            selection_mode=selection_mode,
            requested_model_key=requested_model_key,
            search_snapshot_id=search_snapshot_id,
            context_snapshot_id=context_snapshot_id,
            status=(
                GenerationStatus.ROUTING
                if selection_mode == SelectionMode.AUTO_ROUTE
                else GenerationStatus.GENERATING
            ),
        )
        self.session.add(task)
        self.session.flush()
        return task

    def create_route_snapshot(
        self,
        task: GenerationTask,
        *,
        metadata: dict[str, object],
        candidates: list[dict[str, object]],
    ) -> RouteSnapshot:
        snapshot = RouteSnapshot(
            generation_task_id=task.id,
            user_message_id=task.user_message_id,
            **metadata,
        )
        self.session.add(snapshot)
        self.session.flush()
        for values in candidates:
            self.session.add(RouteCandidate(route_snapshot_id=snapshot.id, **values))
        task.route_snapshot_id = snapshot.id
        task.status = GenerationStatus.GENERATING
        self.session.flush()
        return snapshot

    def append_attempt(self, **values) -> GenerationAttempt:
        task_id = str(values["generation_task_id"])
        current_max = self.session.scalar(
            select(func.max(GenerationAttempt.attempt_index)).where(
                GenerationAttempt.generation_task_id == task_id
            )
        )
        attempt = GenerationAttempt(attempt_index=(current_max or 0) + 1, **values)
        self.session.add(attempt)
        self.session.flush()
        return attempt

    def get_ranked_candidates(self, route_snapshot_id: str) -> list[RouteCandidate]:
        return list(
            self.session.scalars(
                select(RouteCandidate)
                .where(
                    RouteCandidate.route_snapshot_id == route_snapshot_id,
                    RouteCandidate.eligible.is_(True),
                )
                .order_by(RouteCandidate.rank.asc())
            )
        )

    def get_candidate(
        self, route_snapshot_id: str, model_key: str
    ) -> RouteCandidate | None:
        return self.session.scalar(
            select(RouteCandidate).where(
                RouteCandidate.route_snapshot_id == route_snapshot_id,
                RouteCandidate.model_key == model_key,
            )
        )

    @staticmethod
    def succeed_task(task: GenerationTask) -> None:
        task.status = GenerationStatus.SUCCEEDED
        task.completed_at = utc_now()
        task.failure_category = None
        task.failure_message = None

    @staticmethod
    def fail_task(task: GenerationTask, category, message: str) -> None:
        task.status = GenerationStatus.FAILED
        task.failure_category = category
        task.failure_message = message[:500]
        task.completed_at = utc_now()

    def get_details(self, task_id: str) -> GenerationDetails | None:
        task = self.session.get(GenerationTask, task_id)
        if task is None:
            return None
        search = self.session.get(SearchSnapshot, task.search_snapshot_id)
        if search is None:
            return None
        route = (
            self.session.get(RouteSnapshot, task.route_snapshot_id)
            if task.route_snapshot_id
            else None
        )
        candidates = (
            list(
                self.session.scalars(
                    select(RouteCandidate)
                    .where(RouteCandidate.route_snapshot_id == route.id)
                    .order_by(RouteCandidate.model_key.asc())
                )
            )
            if route
            else []
        )
        attempts = list(
            self.session.scalars(
                select(GenerationAttempt)
                .where(GenerationAttempt.generation_task_id == task.id)
                .order_by(GenerationAttempt.attempt_index.asc())
            )
        )
        return GenerationDetails(task, search, route, candidates, attempts)

    def bind_answer_to_task(
        self, answer: AssistantAnswerVersion, task: GenerationTask
    ) -> None:
        answer.generation_task_id = task.id
