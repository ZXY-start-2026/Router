import json
from types import SimpleNamespace

from app.db.models_generation import ContextSnapshot
from app.providers.model import sanitize_completion_text
from app.services.context import ContextService
from app.services.memories import MemoryService


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


def test_memory_prompt_cleans_polluted_assistant_history() -> None:
    turn = SimpleNamespace(
        branch_message=SimpleNamespace(logical_position=1),
        user_message=SimpleNamespace(content="问题"),
        active_answer=SimpleNamespace(
            content=(
                "当前回答。\n\n"
                "User:\n模型自问\n\nAssistant:\n模型自答"
            )
        ),
    )

    prompt = MemoryService._memory_prompt("", "", [turn], [])
    payload = json.loads(prompt.rsplit("\n", 1)[-1])

    assert payload["new_complete_turns"][0]["assistant"] == "当前回答。"


def test_memory_parser_accepts_json_inside_model_explanation() -> None:
    summary, conflicts = MemoryService._parse_model_result(
        '结果如下：```json\n{"summary":"摘要","conflicts":[]}\n```',
        "",
        5,
    )

    assert summary == "摘要"
    assert conflicts["status"] == "CLEAR"

    _, filtered = MemoryService._parse_model_result(
        '{"summary":"摘要","conflicts":'
        '[{"dialogue_position":1,"description":"虚构冲突"}]}',
        "",
        None,
        set(),
    )
    assert filtered["status"] == "CLEAR"
