from app.db.models_generation import ContextSnapshot
from app.providers.model import sanitize_completion_text
from app.services.context import ContextService


def test_sanitizer_keeps_only_the_current_assistant_turn() -> None:
    content = (
        "I am the assistant.\n\n"
        "User:\nhello\n\nAssistant:\nHello again"
    )

    assert sanitize_completion_text(content) == "I am the assistant."


def test_sanitizer_removes_complete_thinking_block() -> None:
    content = "<think>private reasoning</think>\n\nVisible answer"

    assert sanitize_completion_text(content) == "Visible answer"


def test_prompt_cleans_polluted_assistant_history() -> None:
    snapshot = ContextSnapshot(
        user_message_id="message",
        branch_id="branch",
        search_snapshot_id="search",
        system_rules_text="",
        role_text="",
        protected_memory_text="",
        system_memory_text="",
        history_json=[
            {"role": "user", "content": "Who are you?"},
            {
                "role": "assistant",
                "content": (
                    "I am the assistant.\n\n"
                    "User:\nhello\n\nAssistant:\nHello again"
                ),
            },
        ],
        search_context_json={
            "status": "FAILED",
            "failure_message": "",
            "results": [],
        },
        current_user_text="Continue",
    )

    prompt = ContextService.render(snapshot)

    assert "Assistant:\nI am the assistant." in prompt
    assert "User:\nhello" not in prompt
    assert prompt.endswith("User:\nContinue\n\nAssistant:")
