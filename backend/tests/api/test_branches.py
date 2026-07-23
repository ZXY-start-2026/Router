def create_conversation(client) -> dict:
    return client.post("/api/v1/conversations", json={}).json()


def send(client, conversation_id: str, content: str) -> dict:
    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": content, "selection_mode": "AUTO_ROUTE"},
    )
    assert response.status_code == 201
    return response.json()


def test_edit_message_creates_branch_and_preserves_original(client) -> None:
    conversation = create_conversation(client)
    first = send(client, conversation["id"], "原始问题")
    send(client, conversation["id"], "原始后续")
    root_id = conversation["active_branch_id"]

    response = client.patch(
        f"/api/v1/messages/{first['user_message']['id']}",
        json={
            "branch_id": root_id,
            "content": "修改后的问题",
            "selection_mode": "AUTO_ROUTE",
            "model_key": None,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["created_branch_id"] == body["branch_id"]
    assert body["user_message"]["content"] == "修改后的问题"
    assert body["user_message"]["id"] != first["user_message"]["id"]

    edited_history = client.get(
        f"/api/v1/conversations/{conversation['id']}/messages"
    ).json()
    assert [item["user_message"]["content"] for item in edited_history["items"]] == [
        "修改后的问题"
    ]

    client.post(
        f"/api/v1/conversations/{conversation['id']}/branches/{root_id}/activate"
    )
    original_history = client.get(
        f"/api/v1/conversations/{conversation['id']}/messages"
    ).json()
    assert [item["user_message"]["content"] for item in original_history["items"]] == [
        "原始问题",
        "原始后续",
    ]


def test_edit_last_message_still_creates_branch(client) -> None:
    conversation = create_conversation(client)
    sent = send(client, conversation["id"], "最后一条")

    response = client.patch(
        f"/api/v1/messages/{sent['user_message']['id']}",
        json={
            "branch_id": conversation["active_branch_id"],
            "content": "最后一条已修改",
            "selection_mode": "USER_SELECTED",
            "model_key": "MODEL_B",
        },
    )
    assert response.status_code == 201
    assert response.json()["created_branch_id"]
    assert response.json()["active_answer"]["model_key"] == "MODEL_B"


def test_branch_list_and_switch(client) -> None:
    conversation = create_conversation(client)
    sent = send(client, conversation["id"], "主分支消息")
    root_id = conversation["active_branch_id"]
    edited = client.patch(
        f"/api/v1/messages/{sent['user_message']['id']}",
        json={
            "branch_id": root_id,
            "content": "分支消息",
            "selection_mode": "AUTO_ROUTE",
        },
    ).json()

    branches = client.get(
        f"/api/v1/conversations/{conversation['id']}/branches"
    )
    assert branches.status_code == 200
    assert len(branches.json()["items"]) == 2
    assert branches.json()["active_branch_id"] == edited["branch_id"]

    switched = client.post(
        f"/api/v1/conversations/{conversation['id']}/branches/{root_id}/activate"
    )
    assert switched.status_code == 200
    assert switched.json()["active_branch_id"] == root_id


def test_writes_against_inactive_branch_are_rejected(client) -> None:
    conversation = create_conversation(client)
    sent = send(client, conversation["id"], "原分支")
    root_id = conversation["active_branch_id"]
    client.patch(
        f"/api/v1/messages/{sent['user_message']['id']}",
        json={
            "branch_id": root_id,
            "content": "新分支",
            "selection_mode": "AUTO_ROUTE",
        },
    )

    response = client.post(
        f"/api/v1/messages/{sent['user_message']['id']}/regenerations",
        json={
            "branch_id": root_id,
            "mode": "REGENERATE_AUTO_ROUTE",
        },
    )
    assert response.status_code == 409
