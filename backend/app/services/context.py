from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models_core import UserMessage
from app.db.models_generation import ContextSnapshot, SearchSnapshot
from app.providers.search import SearchResponse
from app.repositories.chat import ChatRepository
from app.repositories.generation import GenerationRepository


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

    def prepare(
        self,
        *,
        branch_id: str,
        message: UserMessage,
        search_snapshot: SearchSnapshot,
        search_response: SearchResponse,
    ) -> PreparedContext:
        history: list[dict[str, object]] = []
        for turn in self.chat.list_effective_messages(branch_id):
            if turn.user_message.id == message.id:
                break
            history.append({"role": "user", "content": turn.user_message.content})
            answer = turn.active_answer
            if answer is not None and answer.content is not None:
                history.append({"role": "assistant", "content": answer.content})

        search_context = {
            "provider": search_response.provider,
            "status": search_response.status.value,
            "failure_code": search_response.failure_code,
            "failure_message": search_response.failure_message,
            "results": [
                {"title": item.title, "snippet": item.snippet}
                for item in search_response.results
            ],
        }
        snapshot = self.generation.create_context_snapshot(
            user_message_id=message.id,
            branch_id=branch_id,
            search_snapshot_id=search_snapshot.id,
            system_rules_text=self.settings.system_rules_text,
            role_text="",
            protected_memory_text="",
            system_memory_text="",
            history_json=history,
            search_context_json=search_context,
            current_user_text=message.content,
        )
        return PreparedContext(snapshot=snapshot, prompt=self.render(snapshot))

    @staticmethod
    def render(snapshot: ContextSnapshot) -> str:
        blocks: list[str] = []

        if snapshot.system_rules_text:
            blocks.append(f"System:\n{snapshot.system_rules_text}")

        for item in snapshot.history_json:
            role = "User" if item.get("role") == "user" else "Assistant"
            blocks.append(f"{role}:\n{item.get('content', '')}")

        blocks.append(f"User:\n{snapshot.current_user_text}")
        blocks.append("Assistant:")
        return "\n\n".join(blocks)
