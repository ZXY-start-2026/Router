from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import AnswerVersionStatus, SelectionMode, UserMessageStatus
from app.core.errors import ConflictError
from app.db.models_core import (
    AssistantAnswerVersion,
    Branch,
    BranchMessage,
    UserMessage,
    utc_now,
)


@dataclass(frozen=True, slots=True)
class EffectiveTurn:
    branch_message: BranchMessage
    user_message: UserMessage
    active_answer: AssistantAnswerVersion | None


class ChatRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def append_user_message(
        self, branch: Branch, content: str
    ) -> tuple[UserMessage, BranchMessage]:
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
            logical_position=(current_max or 0) + 1,
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

    def list_effective_messages(self, branch_id: str) -> list[EffectiveTurn]:
        rows = self.session.execute(
            select(BranchMessage, UserMessage, AssistantAnswerVersion)
            .join(UserMessage, UserMessage.id == BranchMessage.user_message_id)
            .outerjoin(
                AssistantAnswerVersion,
                AssistantAnswerVersion.id == BranchMessage.active_answer_version_id,
            )
            .where(BranchMessage.branch_id == branch_id)
            .order_by(BranchMessage.logical_position.asc())
        ).all()
        return [EffectiveTurn(link, message, answer) for link, message, answer in rows]

    def finalize_answer(
        self,
        branch: Branch,
        link: BranchMessage,
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
        if answer.user_message_id != message.id or link.user_message_id != message.id:
            raise ConflictError("回答版本与用户消息不匹配")
        previous_id = link.active_answer_version_id
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
        answer.status = AnswerVersionStatus.SUCCEEDED_ACTIVE
        answer.completed_at = utc_now()
        link.active_answer_version_id = answer.id
        message.status = UserMessageStatus.HAS_ACTIVE_ANSWER
        if previous_id and previous_id != answer.id:
            self._deactivate_if_unreferenced(previous_id)
        branch.complete_turn_count += 1
        return answer

    def mark_answer_failed(
        self,
        message: UserMessage,
        answer: AssistantAnswerVersion,
    ) -> None:
        answer.status = AnswerVersionStatus.FAILED
        answer.completed_at = utc_now()
        message.status = UserMessageStatus.GENERATION_FAILED

    def latest_turn(self, branch_id: str) -> EffectiveTurn | None:
        turns = self.session.execute(
            select(BranchMessage, UserMessage, AssistantAnswerVersion)
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
