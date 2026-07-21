from fastapi.testclient import TestClient


def test_create_conversation_has_root_branch(client: TestClient) -> None:
    response = client.post("/api/v1/conversations", json={})
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "新会话"
    assert body["title_source"] == "DEFAULT"
    assert body["active_branch_id"]


def test_user_title_is_not_automatic(client: TestClient) -> None:
    created = client.post("/api/v1/conversations", json={"title": "手动标题"}).json()
    sent = client.post(
        f"/api/v1/conversations/{created['id']}/messages",
        json={"content": "第一条消息", "selection_mode": "AUTO_ROUTE"},
    )
    assert sent.status_code == 201
    detail = client.get(f"/api/v1/conversations/{created['id']}").json()
    assert detail["title"] == "手动标题"
    assert detail["title_source"] == "USER_EDIT"


def test_first_message_generates_title(client: TestClient) -> None:
    created = client.post("/api/v1/conversations", json={}).json()
    client.post(
        f"/api/v1/conversations/{created['id']}/messages",
        json={"content": "  第一条\n消息  ", "selection_mode": "AUTO_ROUTE"},
    )
    detail = client.get(f"/api/v1/conversations/{created['id']}").json()
    assert detail["title"] == "第一条 消息"
    assert detail["title_source"] == "AUTO_FIRST_MESSAGE"


def test_cursor_pagination_returns_twenty_then_rest(client: TestClient) -> None:
    for index in range(25):
        response = client.post(
            "/api/v1/conversations", json={"title": f"会话 {index:02d}"}
        )
        assert response.status_code == 201

    first = client.get("/api/v1/conversations?limit=20").json()
    assert len(first["items"]) == 20
    assert first["has_more"] is True
    assert first["next_cursor"]

    second = client.get(
        "/api/v1/conversations",
        params={"limit": 20, "cursor": first["next_cursor"]},
    ).json()
    assert len(second["items"]) == 5
    assert second["has_more"] is False
    assert set(item["id"] for item in first["items"]).isdisjoint(
        item["id"] for item in second["items"]
    )


def test_rename_conversation(client: TestClient) -> None:
    created = client.post("/api/v1/conversations", json={}).json()
    response = client.patch(
        f"/api/v1/conversations/{created['id']}", json={"title": "新标题"}
    )
    assert response.status_code == 200
    assert response.json()["title_source"] == "USER_EDIT"

