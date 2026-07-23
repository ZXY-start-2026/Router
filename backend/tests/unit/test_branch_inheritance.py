from sqlalchemy import select

from app.core.enums import (
    AnswerVersionStatus,
    BranchPointType,
    BranchStatus,
    SelectionMode,
    TitleSource,
)
from app.db.models_core import AssistantAnswerVersion, Branch, BranchMessage
from app.repositories.chat import ChatRepository
from app.repositories.conversations import ConversationRepository


def _append_complete_turn(chat, session, branch, content: str):
    message, link = chat.append_user_message(branch, content)
    answer = AssistantAnswerVersion(
        user_message_id=message.id,
        model_key="MODEL_A",
        model_id_snapshot="mock-model",
        selection_mode=SelectionMode.AUTO_ROUTE,
        status=AnswerVersionStatus.SUCCEEDED_ACTIVE,
        content=f"answer:{content}",
    )
    session.add(answer)
    session.flush()
    link.active_answer_version_id = answer.id
    branch.complete_turn_count = chat.count_complete_turns(branch.id)
    return message, link, answer


def test_edit_branch_copies_only_links_before_fork_point(app) -> None:
    with app.state.session_factory() as session:
        conversations = ConversationRepository(session)
        chat = ChatRepository(session)
        conversation = conversations.create_with_root_branch(
            "test", TitleSource.DEFAULT
        )
        root = conversations.get_active_branch(conversation)
        first = _append_complete_turn(chat, session, root, "first")
        second = _append_complete_turn(chat, session, root, "second")
        _append_complete_turn(chat, session, root, "third")

        edited = Branch(
            conversation_id=conversation.id,
            parent_branch_id=root.id,
            branch_point_type=BranchPointType.USER_MESSAGE_EDIT,
            branch_point_message_id=second[0].id,
            status=BranchStatus.ACTIVE,
        )
        session.add(edited)
        session.flush()
        chat.copy_links(root.id, edited.id, second[1].logical_position - 1)
        replacement, _ = chat.append_user_message(
            edited, "replacement", logical_position=second[1].logical_position
        )
        edited.complete_turn_count = chat.count_complete_turns(edited.id)

        links = list(
            session.scalars(
                select(BranchMessage)
                .where(BranchMessage.branch_id == edited.id)
                .order_by(BranchMessage.logical_position)
            )
        )
        assert [item.user_message_id for item in links] == [
            first[0].id,
            replacement.id,
        ]
        assert edited.complete_turn_count == 1
        assert root.complete_turn_count == 3


def test_answer_branch_copies_through_fork_point_and_drops_later_links(app) -> None:
    with app.state.session_factory() as session:
        conversations = ConversationRepository(session)
        chat = ChatRepository(session)
        conversation = conversations.create_with_root_branch(
            "test", TitleSource.DEFAULT
        )
        root = conversations.get_active_branch(conversation)
        _append_complete_turn(chat, session, root, "first")
        second = _append_complete_turn(chat, session, root, "second")
        _append_complete_turn(chat, session, root, "third")

        fork = Branch(
            conversation_id=conversation.id,
            parent_branch_id=root.id,
            branch_point_type=BranchPointType.ANSWER_VERSION_ACTIVATE,
            branch_point_message_id=second[0].id,
            branch_point_answer_version_id=second[2].id,
            status=BranchStatus.ACTIVE,
        )
        session.add(fork)
        session.flush()
        chat.copy_links(root.id, fork.id, second[1].logical_position)
        fork.complete_turn_count = chat.count_complete_turns(fork.id)

        links = list(
            session.scalars(
                select(BranchMessage)
                .where(BranchMessage.branch_id == fork.id)
                .order_by(BranchMessage.logical_position)
            )
        )
        assert [item.logical_position for item in links] == [1, 2]
        assert fork.complete_turn_count == 2
        assert root.complete_turn_count == 3
