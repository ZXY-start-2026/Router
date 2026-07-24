from fastapi.testclient import TestClient

from app.core.errors import ProviderError
from app.providers.model import MockModelProvider


def create_conversation(client: TestClient) -> dict:
    return client.post("/api/v1/conversations", json={}).json()


def send(client: TestClient, conversation_id: str, content: str) -> dict:
    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": content, "selection_mode": "AUTO_ROUTE"},
    )
    assert response.status_code == 201
    return response.json()


def test_edit_list_and_restore_memory_versions(client: TestClient) -> None:
    conversation = create_conversation(client)
    branch_id = conversation["active_branch_id"]

    first = client.put(
        f"/api/v1/branches/{branch_id}/memory",
        json={"protected_user_text": "始终使用中文回答"},
    )
    assert first.status_code == 200
    first_id = first.json()["created_version"]["id"]
    assert first.json()["created_version"]["type"] == "USER_EDIT"

    second = client.put(
        f"/api/v1/branches/{branch_id}/memory",
        json={"protected_user_text": "回答保持简洁"},
    )
    assert second.status_code == 200
    assert second.json()["created_version"]["version_number"] == 2

    history = client.get(f"/api/v1/branches/{branch_id}/memory/versions")
    assert history.status_code == 200
    assert [item["version_number"] for item in history.json()["items"]] == [2, 1]

    restored = client.post(
        f"/api/v1/branches/{branch_id}/memory/versions/{first_id}/restore"
    )
    assert restored.status_code == 200
    body = restored.json()
    assert body["operation_status"] == "SUCCEEDED"
    assert body["created_version"]["type"] == "RESTORE"
    assert body["current"]["protected_user_text"] == "始终使用中文回答"


def test_tenth_complete_turn_creates_initial_summary(client: TestClient) -> None:
    conversation = create_conversation(client)
    for index in range(10):
        result = send(client, conversation["id"], f"第 {index + 1} 轮")
        assert result["generation"]["status"] == "SUCCEEDED"

    memory = client.get(
        f"/api/v1/branches/{conversation['active_branch_id']}/memory"
    )
    assert memory.status_code == 200
    current = memory.json()["current"]
    assert current["type"] == "INITIAL_SYSTEM_SUMMARY"
    assert current["covered_through_position"] == 5
    assert "第 1 轮" in current["system_summary"]


def test_delayed_initial_summary_only_processes_first_batch(
    client: TestClient, app
) -> None:
    allow_memory = False

    def responder(request):
        if request.current_user_text == "[MEMORY_TASK]" and not allow_memory:
            raise ProviderError("摘要暂不可用")
        return MockModelProvider._default_response(request)

    app.state.providers.model._responder = responder
    conversation = create_conversation(client)
    for index in range(14):
        send(client, conversation["id"], f"延迟第 {index + 1} 轮")

    allow_memory = True
    send(client, conversation["id"], "延迟第 15 轮")

    memory = client.get(
        f"/api/v1/branches/{conversation['active_branch_id']}/memory"
    ).json()
    assert memory["current"]["covered_through_position"] == 5
    assert "延迟第 6 轮" not in memory["current"]["system_summary"]


def test_edit_branch_inherits_protected_memory(client: TestClient) -> None:
    conversation = create_conversation(client)
    branch_id = conversation["active_branch_id"]
    client.put(
        f"/api/v1/branches/{branch_id}/memory",
        json={"protected_user_text": "不要使用英文"},
    )
    sent = send(client, conversation["id"], "原消息")
    message_id = sent["user_message"]["id"]

    edited = client.patch(
        f"/api/v1/messages/{message_id}",
        json={
            "branch_id": branch_id,
            "content": "修改后的消息",
            "selection_mode": "AUTO_ROUTE",
            "model_key": None,
        },
    )
    assert edited.status_code == 201
    new_branch_id = edited.json()["branch_id"]
    memory = client.get(f"/api/v1/branches/{new_branch_id}/memory").json()
    assert memory["current"]["type"] == "BRANCH_INHERIT"
    assert memory["current"]["protected_user_text"] == "不要使用英文"
