import pytest

from app.core.enums import (
    AnswerVersionStatus,
    BranchPointType,
    BranchStatus,
    SelectionMode,
    TitleSource,
)
from app.core.errors import ConflictError
from app.db.models_core import AssistantAnswerVersion, Branch, BranchMessage
from app.repositories.chat import ChatRepository
from app.repositories.conversations import ConversationRepository


def _successful_answer(session, message_id: str, status: AnswerVersionStatus):
    answer = AssistantAnswerVersion(
        user_message_id=message_id,
        model_key="MODEL_A",
        model_id_snapshot="mock-model",
        selection_mode=SelectionMode.AUTO_ROUTE,
        status=status,
        content="answer",
    )
    session.add(answer)
    session.flush()
    return answer


def test_old_answer_stays_active_while_another_branch_references_it(app) -> None:
    with app.state.session_factory() as session:
        conversations = ConversationRepository(session)
        chat = ChatRepository(session)
        conversation = conversations.create_with_root_branch(
            "test", TitleSource.DEFAULT
        )
        root = conversations.get_active_branch(conversation)
        message, root_link = chat.append_user_message(root, "question")
        old_answer = _successful_answer(
            session, message.id, AnswerVersionStatus.SUCCEEDED_ACTIVE
        )
        new_answer = _successful_answer(
            session, message.id, AnswerVersionStatus.SUCCEEDED_INACTIVE
        )
        root_link.active_answer_version_id = old_answer.id

        fork = Branch(
            conversation_id=conversation.id,
            parent_branch_id=root.id,
            branch_point_type=BranchPointType.ANSWER_VERSION_ACTIVATE,
            branch_point_message_id=message.id,
            branch_point_answer_version_id=old_answer.id,
            status=BranchStatus.ACTIVE,
        )
        session.add(fork)
        session.flush()
        session.add(
            BranchMessage(
                branch_id=fork.id,
                user_message_id=message.id,
                logical_position=1,
                active_answer_version_id=old_answer.id,
            )
        )
        session.flush()

        chat.activate_answer(root, root_link, message, new_answer)
        session.flush()

        assert old_answer.status == AnswerVersionStatus.SUCCEEDED_ACTIVE
        assert new_answer.status == AnswerVersionStatus.SUCCEEDED_ACTIVE
        assert root.complete_turn_count == 1


def test_failed_answer_cannot_be_activated(app) -> None:
    with app.state.session_factory() as session:
        conversations = ConversationRepository(session)
        chat = ChatRepository(session)
        conversation = conversations.create_with_root_branch(
            "test", TitleSource.DEFAULT
        )
        root = conversations.get_active_branch(conversation)
        message, link = chat.append_user_message(root, "question")
        failed = AssistantAnswerVersion(
            user_message_id=message.id,
            selection_mode=SelectionMode.AUTO_ROUTE,
            status=AnswerVersionStatus.FAILED,
        )
        session.add(failed)
        session.flush()

        with pytest.raises(ConflictError):
            chat.activate_answer(root, link, message, failed)
