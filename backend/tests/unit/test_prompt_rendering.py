from app.db.models_generation import ContextSnapshot
from app.services.context import ContextService


def test_prompt_uses_one_stable_completion_format() -> None:
    snapshot = ContextSnapshot(
        user_message_id="message",
        branch_id="branch",
        search_snapshot_id="search",
        system_rules_text="遵守系统规则",
        role_text="",
        protected_memory_text="",
        system_memory_text="",
        history_json=[
            {"role": "user", "content": "上一问"},
            {"role": "assistant", "content": "上一答"},
        ],
        search_context_json={},
        current_user_text="当前问题",
    )

    assert ContextService.render(snapshot) == (
        "System:\n遵守系统规则\n\n"
        "User:\n上一问\n\nAssistant:\n上一答\n\n"
        "User:\n当前问题\n\nAssistant:"
    )
