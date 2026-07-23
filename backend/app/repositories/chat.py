from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import (
    AnswerVersionStatus,
    AttemptStatus,
    SelectionMode,
    UserMessageStatus,
)
from app.core.errors import ConflictError
from app.db.models_core import (
    AssistantAnswerVersion,
    Branch,
    BranchMessage,
    UserMessage,
    utc_now,
)
from app.db.models_generation import GenerationAttempt


@dataclass(frozen=True, slots=True)
class EffectiveTurn:
    branch_message: BranchMessage
    user_message: UserMessage
    active_answer: AssistantAnswerVersion | None
    finish_reason: str | None


@dataclass(frozen=True, slots=True)
class AnswerWithFinishReason:
    answer: AssistantAnswerVersion
    finish_reason: str | None


class ChatRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def append_user_message(
        self,
        branch: Branch,
        content: str,
        logical_position: int | None = None,
    ) -> tuple[UserMessage, BranchMessage]:
        current_max = None
        if logical_position is None:
            current_max = self.session.scalar(
                select(func.max(BranchMessage.logical_position)).where(
                    BranchMessage.branch_id == branch.id
                )
            )
        message = UserMessage(content=content, status=UserMessageStatus.PENDING)
        self.session.add(message)
        self.session.flush()
        link = BranchMessage(
            branch_id=branch.id,
            user_message_id=message.id,
            logical_position=logical_position or (current_max or 0) + 1,
        )
        self.session.add(link)
        self.session.flush()
        return message, link

    def create_answer_version(
        self,
        user_message_id: str,
        selection_mode: SelectionMode,
    ) -> AssistantAnswerVersion:
        answer = AssistantAnswerVersion(
            user_message_id=user_message_id,
            selection_mode=selection_mode,
            status=AnswerVersionStatus.GENERATING,
        )
        self.session.add(answer)
        self.session.flush()
        return answer

    def get_branch_message(
        self, branch_id: str, message_id: str
    ) -> BranchMessage | None:
        return self.session.scalar(
            select(BranchMessage).where(
                BranchMessage.branch_id == branch_id,
                BranchMessage.user_message_id == message_id,
            )
        )

    def get_message(self, message_id: str) -> UserMessage | None:
        return self.session.get(UserMessage, message_id)

    def get_answer(self, answer_id: str) -> AssistantAnswerVersion | None:
        return self.session.get(AssistantAnswerVersion, answer_id)

    def list_successful_answers(
        self, message_id: str
    ) -> list[AnswerWithFinishReason]:
        rows = self.session.execute(
            select(
                AssistantAnswerVersion,
                self._successful_finish_reason(),
            )
            .where(
                AssistantAnswerVersion.user_message_id == message_id,
                AssistantAnswerVersion.status.in_(
                    (
                        AnswerVersionStatus.SUCCEEDED_ACTIVE,
                        AnswerVersionStatus.SUCCEEDED_INACTIVE,
                    )
                ),
            )
            .order_by(
                AssistantAnswerVersion.created_at.asc(),
                AssistantAnswerVersion.id.asc(),
            )
        ).all()
        return [AnswerWithFinishReason(*row) for row in rows]

    def has_later_messages(self, branch_id: str, position: int) -> bool:
        return bool(
            self.session.scalar(
                select(func.count())
                .select_from(BranchMessage)
                .where(
                    BranchMessage.branch_id == branch_id,
                    BranchMessage.logical_position > position,
                )
            )
        )

    def copy_links(
        self,
        source_branch_id: str,
        target_branch_id: str,
        end_position: int,
    ) -> list[BranchMessage]:
        source = list(
            self.session.scalars(
                select(BranchMessage)
                .where(
                    BranchMessage.branch_id == source_branch_id,
                    BranchMessage.logical_position <= end_position,
                )
                .order_by(BranchMessage.logical_position.asc())
            )
        )
        copies = [
            BranchMessage(
                branch_id=target_branch_id,
                user_message_id=item.user_message_id,
                logical_position=item.logical_position,
                active_answer_version_id=item.active_answer_version_id,
            )
            for item in source
        ]
        self.session.add_all(copies)
        self.session.flush()
        return copies

    def list_effective_messages(self, branch_id: str) -> list[EffectiveTurn]:
        rows = self.session.execute(
            select(
                BranchMessage,
                UserMessage,
                AssistantAnswerVersion,
                self._successful_finish_reason(),
            )
            .join(UserMessage, UserMessage.id == BranchMessage.user_message_id)
            .outerjoin(
                AssistantAnswerVersion,
                AssistantAnswerVersion.id == BranchMessage.active_answer_version_id,
            )
            .where(BranchMessage.branch_id == branch_id)
            .order_by(BranchMessage.logical_position.asc())
        ).all()
        return [EffectiveTurn(*row) for row in rows]

    def complete_answer(
        self,
        message: UserMessage,
        answer: AssistantAnswerVersion,
        *,
        content: str,
        model_key: str,
        model_id: str,
        display_name: str,
        selection_mode: SelectionMode,
        route_snapshot_id: str | None,
        predicted_input_tokens: int | None,
        predicted_output_tokens: int | None,
        predicted_cost: Decimal | None,
        actual_input_tokens: int,
        actual_output_tokens: int,
        actual_cost: Decimal,
        price_version: str,
    ) -> AssistantAnswerVersion:
        if answer.user_message_id != message.id:
            raise ConflictError("回答版本与用户消息不匹配")
        answer.content = content
        answer.model_key = model_key
        answer.display_name_snapshot = display_name
        answer.model_id_snapshot = model_id
        answer.selection_mode = selection_mode
        answer.route_snapshot_id = route_snapshot_id
        answer.predicted_input_tokens = predicted_input_tokens
        answer.predicted_output_tokens = predicted_output_tokens
        answer.actual_input_tokens = actual_input_tokens
        answer.actual_output_tokens = actual_output_tokens
        answer.predicted_cost = predicted_cost
        answer.actual_cost = actual_cost
        answer.input_token_error = (
            actual_input_tokens - predicted_input_tokens
            if predicted_input_tokens is not None
            else None
        )
        answer.output_token_error = (
            actual_output_tokens - predicted_output_tokens
            if predicted_output_tokens is not None
            else None
        )
        answer.cost_error = (
            actual_cost - predicted_cost if predicted_cost is not None else None
        )
        answer.price_version = price_version
        answer.status = AnswerVersionStatus.SUCCEEDED_INACTIVE
        answer.completed_at = utc_now()
        return answer

    def activate_answer(
        self,
        branch: Branch,
        link: BranchMessage,
        message: UserMessage,
        answer: AssistantAnswerVersion,
    ) -> AssistantAnswerVersion:
        if answer.user_message_id != message.id or link.user_message_id != message.id:
            raise ConflictError("回答版本与用户消息不匹配")
        if answer.status not in {
            AnswerVersionStatus.SUCCEEDED_ACTIVE,
            AnswerVersionStatus.SUCCEEDED_INACTIVE,
        }:
            raise ConflictError("只有成功回答可以设为当前版本")
        previous_id = link.active_answer_version_id
        link.active_answer_version_id = answer.id
        answer.status = AnswerVersionStatus.SUCCEEDED_ACTIVE
        message.status = UserMessageStatus.HAS_ACTIVE_ANSWER
        self.session.flush()
        if previous_id and previous_id != answer.id:
            self._deactivate_if_unreferenced(previous_id)
        branch.complete_turn_count = self.count_complete_turns(branch.id)
        return answer

    def finalize_answer(
        self,
        branch: Branch,
        link: BranchMessage,
        message: UserMessage,
        answer: AssistantAnswerVersion,
        **values,
    ) -> AssistantAnswerVersion:
        self.complete_answer(message, answer, **values)
        return self.activate_answer(branch, link, message, answer)

    def mark_answer_failed(
        self,
        message: UserMessage,
        answer: AssistantAnswerVersion,
    ) -> None:
        answer.status = AnswerVersionStatus.FAILED
        answer.completed_at = utc_now()
        self.session.flush()
        self.refresh_message_status(message.id)

    def count_complete_turns(self, branch_id: str) -> int:
        return int(
            self.session.scalar(
                select(func.count())
                .select_from(BranchMessage)
                .join(
                    AssistantAnswerVersion,
                    AssistantAnswerVersion.id == BranchMessage.active_answer_version_id,
                )
                .where(
                    BranchMessage.branch_id == branch_id,
                    AssistantAnswerVersion.status.in_(
                        (
                            AnswerVersionStatus.SUCCEEDED_ACTIVE,
                            AnswerVersionStatus.SUCCEEDED_INACTIVE,
                        )
                    ),
                )
            )
            or 0
        )

    def refresh_message_status(self, message_id: str) -> None:
        message = self.session.get(UserMessage, message_id)
        if message is None:
            return
        active_references = self.session.scalar(
            select(func.count())
            .select_from(BranchMessage)
            .where(
                BranchMessage.user_message_id == message_id,
                BranchMessage.active_answer_version_id.is_not(None),
            )
        )
        message.status = (
            UserMessageStatus.HAS_ACTIVE_ANSWER
            if active_references
            else UserMessageStatus.GENERATION_FAILED
        )

    def latest_turn(self, branch_id: str) -> EffectiveTurn | None:
        turns = self.session.execute(
            select(
                BranchMessage,
                UserMessage,
                AssistantAnswerVersion,
                self._successful_finish_reason(),
            )
            .join(UserMessage, UserMessage.id == BranchMessage.user_message_id)
            .outerjoin(
                AssistantAnswerVersion,
                AssistantAnswerVersion.id == BranchMessage.active_answer_version_id,
            )
            .where(BranchMessage.branch_id == branch_id)
            .order_by(BranchMessage.logical_position.desc())
            .limit(1)
        ).first()
        if turns is None:
            return None
        return EffectiveTurn(*turns)

    @staticmethod
    def _successful_finish_reason():
        return (
            select(GenerationAttempt.finish_reason)
            .where(
                GenerationAttempt.generation_task_id
                == AssistantAnswerVersion.generation_task_id,
                GenerationAttempt.status == AttemptStatus.SUCCEEDED,
            )
            .order_by(GenerationAttempt.attempt_index.desc())
            .limit(1)
            .correlate(AssistantAnswerVersion)
            .scalar_subquery()
        )

    def _deactivate_if_unreferenced(self, answer_id: str) -> None:
        references = self.session.scalar(
            select(func.count()).select_from(BranchMessage).where(
                BranchMessage.active_answer_version_id == answer_id
            )
        )
        if not references:
            previous = self.session.get(AssistantAnswerVersion, answer_id)
            if previous and previous.status == AnswerVersionStatus.SUCCEEDED_ACTIVE:
                previous.status = AnswerVersionStatus.SUCCEEDED_INACTIVE
