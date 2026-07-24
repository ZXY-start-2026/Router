from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models_core import UserMessage
from app.db.models_generation import ContextSnapshot, SearchSnapshot
from app.providers.model import sanitize_completion_text
from app.repositories.chat import ChatRepository
from app.repositories.generation import GenerationRepository
from app.repositories.memories import MemoryRepository
from app.repositories.roles import RoleRepository
from app.services.roles import RoleService


@dataclass(frozen=True, slots=True)
class PreparedContext:
    snapshot: ContextSnapshot
    prompt: str


class ContextService:
    """Builds one immutable context and renders the prompt exactly once."""

    def __init__(self, session: Session, settings: Settings) -> None:
        self.settings = settings
        self.chat = ChatRepository(session)
        self.generation = GenerationRepository(session)
        self.memories = MemoryRepository(session)
        self.roles = RoleRepository(session)

    def prepare(
        self,
        *,
        branch_id: str,
        message: UserMessage,
        search_snapshot: SearchSnapshot,
    ) -> PreparedContext:
        memory = self.memories.get_current(branch_id)
        role = self.roles.get_current_for_branch(branch_id)
        covered_through = memory.covered_through_position if memory else None
        history: list[dict[str, object]] = []
        for turn in self.chat.list_effective_messages(branch_id):
            if turn.user_message.id == message.id:
                break
            if turn.active_answer is None or turn.active_answer.content is None:
                continue
            if (
                covered_through is not None
                and turn.branch_message.logical_position <= covered_through
            ):
                continue
            history.append(
                {
                    "role": "user",
                    "content": turn.user_message.content,
                    "user_message_id": turn.user_message.id,
                    "branch_message_id": turn.branch_message.id,
                }
            )
            history.append(
                {
                    "role": "assistant",
                    "content": turn.active_answer.content,
                    "answer_version_id": turn.active_answer.id,
                }
            )

        results = self.generation.list_search_results(search_snapshot.id)
        search_context = {
            "provider": search_snapshot.provider,
            "status": search_snapshot.status.value,
            "failure_code": search_snapshot.failure_code,
            "failure_message": search_snapshot.failure_message,
            "results": [
                {"title": item.title, "snippet": item.snippet}
                for item in results
            ],
        }
        snapshot = self.generation.create_context_snapshot(
            user_message_id=message.id,
            branch_id=branch_id,
            search_snapshot_id=search_snapshot.id,
            memory_version_id=memory.id if memory else None,
            role_version_id=role.id if role else None,
            system_rules_text=self.settings.system_rules_text,
            role_text=RoleService.render(role),
            protected_memory_text=memory.protected_user_text if memory else "",
            system_memory_text=memory.system_summary if memory else "",
            history_json=history,
            search_context_json=search_context,
            current_user_text=message.content,
        )
        return PreparedContext(snapshot=snapshot, prompt=self.render(snapshot))

    @staticmethod
    def render(snapshot: ContextSnapshot) -> str:
        system_parts = [
            snapshot.system_rules_text,
            snapshot.role_text,
            snapshot.system_memory_text,
            snapshot.protected_memory_text,
            ContextService._search_text(snapshot.search_context_json),
        ]
        blocks: list[str] = []
        non_empty_system = [part for part in system_parts if part]
        if non_empty_system:
            blocks.append("System:\n" + "\n\n".join(non_empty_system))
        for item in snapshot.history_json:
            role = "User" if item.get("role") == "user" else "Assistant"
            content = str(item.get("content", ""))
            if role == "Assistant":
                content = sanitize_completion_text(content)
            blocks.append(f"{role}:\n{content}")
        blocks.append(f"User:\n{snapshot.current_user_text}")
        blocks.append("Assistant:")
        return "\n\n".join(blocks)

    @staticmethod
    def _search_text(value: dict[str, object]) -> str:
        status = str(value.get("status", "FAILED"))
        results = value.get("results")
        if isinstance(results, list) and results:
            lines = ["联网搜索上下文："]
            for index, item in enumerate(results, start=1):
                if isinstance(item, dict):
                    lines.append(
                        f"{index}. {item.get('title', '')}\n{item.get('snippet', '')}"
                    )
            return "\n".join(lines)
        message = value.get("failure_message")
        if message:
            return f"联网搜索状态：{status}。{message}"
        return f"联网搜索状态：{status}，未获得有效结果。"
