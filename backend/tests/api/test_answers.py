from sqlalchemy import func, select

from app.db.models_core import AssistantAnswerVersion, Branch
from app.db.models_generation import RouteSnapshot, SearchSnapshot


def create_conversation(client) -> dict:
    return client.post("/api/v1/conversations", json={}).json()


def send(client, conversation_id: str, content: str) -> dict:
    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": content, "selection_mode": "AUTO_ROUTE"},
    )
    assert response.status_code == 201
    return response.json()


def test_regenerate_auto_reuses_search_and_lists_successful_versions(
    client, app
) -> None:
    conversation = create_conversation(client)
    original = send(client, conversation["id"], "需要多个版本")
    message_id = original["user_message"]["id"]
    branch_id = conversation["active_branch_id"]

    response = client.post(
        f"/api/v1/messages/{message_id}/regenerations",
        json={
            "branch_id": branch_id,
            "mode": "REGENERATE_AUTO_ROUTE",
            "model_key": None,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["generation"]["status"] == "SUCCEEDED"
    assert body["created_branch_id"] is None
    assert body["active_answer"]["id"] != original["active_answer"]["id"]

    versions = client.get(
        f"/api/v1/messages/{message_id}/answers",
        params={"branch_id": branch_id},
    )
    assert versions.status_code == 200
    version_body = versions.json()
    assert len(version_body["items"]) == 2
    assert version_body["active_answer_version_id"] == body["active_answer"]["id"]

    with app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(SearchSnapshot)) == 1
        assert session.scalar(select(func.count()).select_from(RouteSnapshot)) == 2


def test_regenerate_original_model_skips_new_route_snapshot(client, app) -> None:
    conversation = create_conversation(client)
    original = send(client, conversation["id"], "沿用原模型")

    response = client.post(
        f"/api/v1/messages/{original['user_message']['id']}/regenerations",
        json={
            "branch_id": conversation["active_branch_id"],
            "mode": "REGENERATE_ORIGINAL_MODEL",
        },
    )
    assert response.status_code == 201
    assert response.json()["active_answer"]["model_key"] == "MODEL_A"
    with app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(RouteSnapshot)) == 1


def test_historical_regeneration_creates_branch_without_changing_original(
    client, app
) -> None:
    conversation = create_conversation(client)
    first = send(client, conversation["id"], "第一条")
    send(client, conversation["id"], "第二条")
    root_branch_id = conversation["active_branch_id"]
    old_answer_id = first["active_answer"]["id"]

    response = client.post(
        f"/api/v1/messages/{first['user_message']['id']}/regenerations",
        json={
            "branch_id": root_branch_id,
            "mode": "REGENERATE_AUTO_ROUTE",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["created_branch_id"]
    assert body["branch_id"] == body["created_branch_id"]

    new_history = client.get(
        f"/api/v1/conversations/{conversation['id']}/messages"
    ).json()
    assert len(new_history["items"]) == 1
    assert new_history["items"][0]["active_answer"]["id"] != old_answer_id

    client.post(
        f"/api/v1/conversations/{conversation['id']}/branches/{root_branch_id}/activate"
    )
    old_history = client.get(
        f"/api/v1/conversations/{conversation['id']}/messages"
    ).json()
    assert len(old_history["items"]) == 2
    assert old_history["items"][0]["active_answer"]["id"] == old_answer_id

    with app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Branch)) == 2


def test_failed_answer_cannot_be_activated(client, app) -> None:
    conversation = create_conversation(client)
    sent = send(client, conversation["id"], "成功回答")
    with app.state.session_factory() as session:
        failed = AssistantAnswerVersion(
            user_message_id=sent["user_message"]["id"],
            selection_mode="AUTO_ROUTE",
            status="FAILED",
        )
        session.add(failed)
        session.commit()
        failed_id = failed.id

    response = client.post(
        f"/api/v1/messages/{sent['user_message']['id']}/answers/{failed_id}/activate",
        json={"branch_id": conversation["active_branch_id"]},
    )
    assert response.status_code == 409
