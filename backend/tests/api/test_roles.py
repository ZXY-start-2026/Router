from fastapi.testclient import TestClient


def create_conversation(client: TestClient) -> dict:
    return client.post("/api/v1/conversations", json={}).json()


def role_payload(name: str = "技术顾问") -> dict:
    return {
        "name": name,
        "persona": "务实的工程师",
        "background": "有大型系统经验",
        "domain": "软件架构",
        "traits": ["严谨", "简洁", "严谨"],
        "style": "先给结论",
        "constraints_text": "不虚构事实",
    }


def test_role_template_save_and_deactivate(client: TestClient) -> None:
    conversation = create_conversation(client)
    template = client.post("/api/v1/role-templates", json=role_payload())
    assert template.status_code == 201
    template_id = template.json()["id"]

    payload = role_payload()
    payload["source_template_id"] = template_id
    saved = client.put(
        f"/api/v1/conversations/{conversation['id']}/role",
        json=payload,
    )
    assert saved.status_code == 200
    role = saved.json()["active_role"]
    assert role["version_number"] == 1
    assert role["source_template_id"] == template_id
    assert role["traits"] == ["严谨", "简洁"]

    current = client.get(
        f"/api/v1/conversations/{conversation['id']}/role"
    )
    assert current.json()["active_role"]["domain"] == "软件架构"

    deactivated = client.post(
        f"/api/v1/conversations/{conversation['id']}/role/deactivate"
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["active_role"] is None


def test_edit_branch_inherits_role_used_at_fork(client: TestClient) -> None:
    conversation = create_conversation(client)
    client.put(
        f"/api/v1/conversations/{conversation['id']}/role",
        json=role_payload("原角色"),
    )
    sent = client.post(
        f"/api/v1/conversations/{conversation['id']}/messages",
        json={"content": "原问题", "selection_mode": "AUTO_ROUTE"},
    ).json()

    edited = client.patch(
        f"/api/v1/messages/{sent['user_message']['id']}",
        json={
            "branch_id": conversation["active_branch_id"],
            "content": "修改后的问题",
            "selection_mode": "AUTO_ROUTE",
            "model_key": None,
        },
    )
    assert edited.status_code == 201
    current = client.get(
        f"/api/v1/conversations/{conversation['id']}/role"
    ).json()
    assert current["branch_id"] == edited.json()["branch_id"]
    assert current["active_role"]["name"] == "原角色"
