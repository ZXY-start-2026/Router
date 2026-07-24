from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.enums import (
    MemoryOperationStatus,
    MemoryVersionType,
)
from app.core.errors import ConflictError, NotFoundError, ProviderError
from app.db.models_core import Branch
from app.db.models_memory import MemoryUpdateRecord, MemoryVersion
from app.providers.model import ModelRequest, sanitize_completion_text
from app.providers.registry import ProviderRegistry
from app.repositories.chat import ChatRepository, EffectiveTurn
from app.repositories.conversations import ConversationRepository
from app.repositories.memories import MemoryRepository
from app.schemas.memories import (
    CurrentMemoryResponse,
    MemoryConfigResponse,
    MemoryOperationResponse,
    MemoryUpdateStatusResponse,
    MemoryVersionResponse,
    MemoryVersionsResponse,
)


@dataclass(frozen=True, slots=True)
class MemoryUpdateOutcome:
    status: str
    version: MemoryVersion | None = None

@dataclass(frozen=True, slots=True)
class SummaryResult:
    summary: str
    conflicts: dict[str, object]
    attempts: int


class MemoryService:
    def __init__(
        self, session: Session, settings: Settings, providers: ProviderRegistry
    ) -> None:
        self.session = session
        self.settings = settings
        self.providers = providers
        self.memories = MemoryRepository(session)
        self.chat = ChatRepository(session)
        self.conversations = ConversationRepository(session)

    def get_current(self, branch_id: str) -> CurrentMemoryResponse:
        branch = self._require_branch(branch_id)
        current = self.memories.get_current(branch.id)
        latest = self.memories.latest_update(branch.id)
        return CurrentMemoryResponse(
            branch_id=branch.id,
            current=self._version_response(current, branch) if current else None,
            latest_update=self._update_response(latest) if latest else None,
            config=MemoryConfigResponse(
                n=self.settings.memory.n,
                k=self.settings.memory.k,
                m=self.settings.memory.m,
            ),
        )

    def list_versions(
        self, branch_id: str, limit: int, cursor: str | None
    ) -> MemoryVersionsResponse:
        branch = self._require_branch(branch_id)
        items, next_cursor, has_more = self.memories.list_versions(
            branch.id, limit, cursor
        )
        return MemoryVersionsResponse(
            items=[self._version_response(item, branch) for item in items],
            next_cursor=next_cursor,
            has_more=has_more,
        )

    def edit_protected_text(
        self, branch_id: str, text: str
    ) -> MemoryOperationResponse:
        branch = self._require_active_branch(branch_id)
        current = self.memories.get_current(branch.id)
        turns = self._complete_turns(branch.id)
        conflict = self.detect_conflicts(text, turns)
        version = self.memories.create_version(
            branch_id=branch.id,
            version_type=MemoryVersionType.USER_EDIT,
            base_version_id=current.id if current else None,
            protected_user_text=text,
            system_summary=current.system_summary if current else "",
            covered_through_position=(
                current.covered_through_position if current else None
            ),
            conflict_metadata=conflict,
        )
        self.memories.set_current(branch, version)
        self.session.commit()
        return self._operation_response(branch, version)

    def restore(self, branch_id: str, version_id: str) -> MemoryOperationResponse:
        branch = self._require_active_branch(branch_id)
        source = self.memories.get_version(version_id)
        if source is None:
            raise NotFoundError("备忘录版本不存在")
        if source.branch_id != branch.id:
            raise ConflictError("备忘录版本不属于目标分支")
        current = self.memories.get_current(branch.id)
        turns = self._complete_turns(branch.id)
        eligible = turns[: max(0, len(turns) - self.settings.memory.k)]
        missing = [
            turn
            for turn in eligible
            if turn.branch_message.logical_position
            > (source.covered_through_position or 0)
        ]
        summary = source.system_summary
        conflict = self._clear_conflicts(
            turns[-self.settings.memory.k :] if self.settings.memory.k else []
        )
        record: MemoryUpdateRecord | None = None
        attempts = 0
        if missing:
            record = self.memories.create_update_record(
                branch_id=branch.id,
                base_version_id=current.id if current else None,
                from_position=missing[0].branch_message.logical_position,
                through_position=missing[-1].branch_message.logical_position,
            )
            self.session.commit()
            try:
                result = self._summarize(
                    summary,
                    source.protected_user_text,
                    missing,
                    turns[-self.settings.memory.k :] if self.settings.memory.k else [],
                )
                summary, conflict, attempts = (
                    result.summary,
                    result.conflicts,
                    result.attempts,
                )
            except ProviderError as error:
                self.memories.finish_update(
                    record,
                    attempt_count=max(1, attempts),
                    error_category=error.category.value,
                    error_message=error.message,
                )
                self.session.commit()
                return self._operation_response(branch, None, failed=True)
        elif source.protected_user_text:
            conflict = self.detect_conflicts(source.protected_user_text, turns)

        target_position = (
            eligible[-1].branch_message.logical_position
            if eligible
            else source.covered_through_position
        )
        version = self.memories.create_version(
            branch_id=branch.id,
            version_type=MemoryVersionType.RESTORE,
            base_version_id=current.id if current else None,
            restored_from_version_id=source.id,
            protected_user_text=source.protected_user_text,
            system_summary=summary,
            covered_through_position=target_position,
            added_from_position=(
                missing[0].branch_message.logical_position if missing else None
            ),
            added_through_position=(
                missing[-1].branch_message.logical_position if missing else None
            ),
            conflict_metadata=conflict,
        )
        self.memories.set_current(branch, version)
        if record:
            self.memories.finish_update(
                record, version=version, attempt_count=max(1, attempts)
            )
        self.session.commit()
        return self._operation_response(branch, version)

    def update_if_due(self, branch_id: str) -> MemoryUpdateOutcome:
        branch = self._require_branch(branch_id)
        turns = self._complete_turns(branch.id)
        current = self.memories.get_current(branch.id)
        eligible_count = max(0, len(turns) - self.settings.memory.k)
        if eligible_count <= 0:
            return MemoryUpdateOutcome("SKIPPED")
        covered_position = (
            current.covered_through_position or 0 if current is not None else 0
        )
        covered_count = sum(
            1
            for turn in turns
            if turn.branch_message.logical_position
            <= covered_position
        )
        if not current or not current.system_summary:
            if len(turns) < self.settings.memory.n:
                return MemoryUpdateOutcome("SKIPPED")
        elif eligible_count - covered_count < self.settings.memory.m:
            return MemoryUpdateOutcome("SKIPPED")

        batch_size = self.settings.memory.n - self.settings.memory.k if not current or not current.system_summary else self.settings.memory.m
        missing = turns[covered_count : min(covered_count + batch_size, eligible_count)]
        if not missing:
            return MemoryUpdateOutcome("SKIPPED")
        record = self.memories.create_update_record(
            branch_id=branch.id,
            base_version_id=current.id if current else None,
            from_position=missing[0].branch_message.logical_position,
            through_position=missing[-1].branch_message.logical_position,
        )
        self.session.commit()
        try:
            result = self._summarize(
                current.system_summary if current else "",
                current.protected_user_text if current else "",
                missing,
                turns[eligible_count:],
            )
        except ProviderError as error:
            self.memories.finish_update(
                record,
                attempt_count=2 if error.retryable else 1,
                error_category=error.category.value,
                error_message=error.message,
            )
            self.session.commit()
            return MemoryUpdateOutcome("FAILED")

        version = self.memories.create_version(
            branch_id=branch.id,
            version_type=(
                MemoryVersionType.INITIAL_SYSTEM_SUMMARY
                if not current or not current.system_summary
                else MemoryVersionType.INCREMENTAL_SYSTEM_UPDATE
            ),
            base_version_id=current.id if current else None,
            protected_user_text=current.protected_user_text if current else "",
            system_summary=result.summary,
            covered_through_position=missing[-1].branch_message.logical_position,
            added_from_position=missing[0].branch_message.logical_position,
            added_through_position=missing[-1].branch_message.logical_position,
            conflict_metadata=result.conflicts,
        )
        self.memories.set_current(branch, version)
        self.memories.finish_update(
            record, version=version, attempt_count=result.attempts
        )
        self.session.commit()
        return MemoryUpdateOutcome("UPDATED", version)

    def inherit_for_branch(
        self, source: Branch, target: Branch, fork_position: int
    ) -> MemoryVersion | None:
        inherited = self.memories.find_inheritable(source.id, fork_position)
        if inherited is None:
            return None
        version = self.memories.create_version(
            branch_id=target.id,
            version_type=MemoryVersionType.BRANCH_INHERIT,
            inherited_from_version_id=inherited.id,
            protected_user_text=inherited.protected_user_text,
            system_summary=inherited.system_summary,
            covered_through_position=inherited.covered_through_position,
            conflict_metadata=inherited.conflict_metadata_json,
        )
        self.memories.set_current(target, version)
        return version

    def detect_conflicts(
        self, text: str, turns: list[EffectiveTurn]
    ) -> dict[str, object]:
        if not text:
            return self._clear_conflicts(turns)
        try:
            result = self._summarize("", text, [], turns)
            return result.conflicts
        except ProviderError:
            return {
                "status": "UNKNOWN",
                "checked_through_position": self._last_position(turns),
                "items": [],
            }

    def _summarize(
        self,
        current_summary: str,
        protected_text: str,
        new_turns: list[EffectiveTurn],
        recent_turns: list[EffectiveTurn],
    ) -> SummaryResult:
        prompt = self._memory_prompt(
            current_summary, protected_text, new_turns, recent_turns
        )
        last_error: ProviderError | None = None
        for attempt in range(1, 3):
            try:
                result = self.providers.model.generate(
                    ModelRequest(
                        prompt=prompt,
                        current_user_text="[MEMORY_TASK]",
                        requested_model_key=self.settings.memory.model_id,
                    )
                )
                summary, conflicts = self._parse_model_result(
                    result.content,
                    current_summary,
                    self._last_position(recent_turns),
                    {turn.branch_message.logical_position for turn in recent_turns},
                )
                return SummaryResult(summary, conflicts, attempt)
            except ProviderError as error:
                last_error = error
                if attempt == 1 and error.retryable:
                    continue
                raise
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ProviderError(
                    "备忘录模型返回格式无效",
                    provider_code="MEMORY_RESPONSE_INVALID",
                ) from exc
        assert last_error is not None
        raise last_error

    @staticmethod
    def _parse_model_result(
        content: str,
        fallback_summary: str,
        checked_position: int | None,
        valid_conflict_positions: set[int] | None = None,
    ) -> tuple[str, dict[str, object]]:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError:
            start, end = cleaned.find("{"), cleaned.rfind("}")
            if start < 0 or end <= start:
                raise
            payload = json.loads(cleaned[start : end + 1])
        if not isinstance(payload, dict):
            raise ValueError("memory result")
        summary = payload.get("summary", fallback_summary)
        items = payload.get("conflicts", [])
        if not isinstance(summary, str) or not isinstance(items, list):
            raise ValueError("memory result fields")
        normalized_items = [
            {
                "dialogue_position": item.get("dialogue_position"),
                "description": str(item.get("description", ""))[:500],
            }
            for item in items
            if isinstance(item, dict) and str(item.get("description", "")).strip()
            and (
                valid_conflict_positions is None
                or item.get("dialogue_position") in valid_conflict_positions
            )
        ]
        summary = summary.strip()
        if len(summary) > 2000: raise ValueError("memory summary too long")
        return summary, {
            "status": "CONFLICT" if normalized_items else "CLEAR",
            "checked_through_position": checked_position,
            "items": normalized_items,
        }

    @staticmethod
    def _memory_prompt(
        current_summary: str,
        protected_text: str,
        new_turns: list[EffectiveTurn],
        recent_turns: list[EffectiveTurn],
    ) -> str:
        def serialize(turns: list[EffectiveTurn]) -> list[dict[str, object]]:
            return [
                {
                    "position": turn.branch_message.logical_position,
                    "user": turn.user_message.content,
                    "assistant": (
                        sanitize_completion_text(turn.active_answer.content)
                        if turn.active_answer and turn.active_answer.content
                        else ""
                    ),
                }
                for turn in turns
            ]

        payload = {
            "current_summary": current_summary,
            "protected_user_text": protected_text,
            "new_complete_turns": serialize(new_turns),
            "recent_complete_turns": serialize(recent_turns),
        }
        return (
            "[MEMORY_TASK]\n"
            "请仅返回 JSON：{\"summary\":\"增量更新后的摘要\",\"conflicts\":[]}。"
            "仅当最近对话与保护区明确矛盾时，conflicts 才加入"
            "{\"dialogue_position\":对话位置,\"description\":\"冲突说明\"}。"
            "摘要不超过1200个中文字符且不得逐轮复述；不得改写保护区；没有新增轮次时 summary 保持原值。\n"
            + json.dumps(payload, ensure_ascii=False)
        )

    def _complete_turns(self, branch_id: str) -> list[EffectiveTurn]:
        return [
            turn
            for turn in self.chat.list_effective_messages(branch_id)
            if turn.active_answer is not None and turn.active_answer.content is not None
        ]

    def _require_branch(self, branch_id: str) -> Branch:
        branch = self.conversations.get_branch(branch_id)
        if branch is None:
            raise NotFoundError("分支不存在")
        return branch

    def _require_active_branch(self, branch_id: str) -> Branch:
        branch = self._require_branch(branch_id)
        conversation = self.conversations.get(branch.conversation_id)
        if conversation is None:
            raise NotFoundError("会话不存在")
        if conversation.active_branch_id != branch.id:
            raise ConflictError("只能操作当前活动分支")
        return branch

    def _operation_response(
        self, branch: Branch, version: MemoryVersion | None, failed: bool = False
    ) -> MemoryOperationResponse:
        current = self.memories.get_current(branch.id)
        latest = self.memories.latest_update(branch.id)
        return MemoryOperationResponse(
            branch_id=branch.id,
            operation_status=(
                MemoryOperationStatus.FAILED
                if failed
                else MemoryOperationStatus.SUCCEEDED
            ),
            current=self._version_response(current, branch) if current else None,
            created_version=(
                self._version_response(version, branch) if version else None
            ),
            latest_update=self._update_response(latest) if latest else None,
        )

    @staticmethod
    def _version_response(
        version: MemoryVersion, branch: Branch
    ) -> MemoryVersionResponse:
        return MemoryVersionResponse(
            id=version.id,
            branch_id=version.branch_id,
            version_number=version.version_number,
            type=version.type,
            base_version_id=version.base_version_id,
            restored_from_version_id=version.restored_from_version_id,
            inherited_from_version_id=version.inherited_from_version_id,
            protected_user_text=version.protected_user_text,
            system_summary=version.system_summary,
            covered_through_position=version.covered_through_position,
            added_from_position=version.added_from_position,
            added_through_position=version.added_through_position,
            conflict_metadata=version.conflict_metadata_json,
            created_at=version.created_at,
            is_current=branch.active_memory_version_id == version.id,
        )

    @staticmethod
    def _update_response(record: MemoryUpdateRecord) -> MemoryUpdateStatusResponse:
        return MemoryUpdateStatusResponse(
            id=record.id,
            status=record.status,
            target_from_position=record.target_from_position,
            target_through_position=record.target_through_position,
            attempt_count=record.attempt_count,
            error_category=record.error_category,
            error_message=record.error_message,
            created_at=record.created_at,
            completed_at=record.completed_at,
            created_memory_version_id=record.created_memory_version_id,
        )

    @staticmethod
    def _last_position(turns: list[EffectiveTurn]) -> int | None:
        return turns[-1].branch_message.logical_position if turns else None

    def _clear_conflicts(
        self, turns: list[EffectiveTurn]
    ) -> dict[str, object]:
        return {
            "status": "CLEAR",
            "checked_through_position": self._last_position(turns),
            "items": [],
        }
