from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import Settings
from app.db.models_core import AssistantAnswerVersion, BranchMessage, UserMessage
from app.db.session import Base
from app.main import create_app
from app.providers.model import ModelResult, UnavailableModelProvider


def create_conversation(client: TestClient) -> dict:
    return client.post("/api/v1/conversations", json={}).json()


def test_send_message_saves_active_answer(client: TestClient, app) -> None:
    conversation = create_conversation(client)
    response = client.post(
        f"/api/v1/conversations/{conversation['id']}/messages",
        json={"content": "你好", "selection_mode": "AUTO_ROUTE"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["generation"]["status"] == "SUCCEEDED"
    assert body["active_answer"]["content"] == "Mock 回复：你好"
    assert body["active_answer"]["model_key"] == "MODEL_A"
    assert body["active_answer"]["finish_reason"] == "stop"

    with app.state.session_factory() as session:
        links = session.scalar(select(func.count()).select_from(BranchMessage))
        active = session.scalar(
            select(func.count()).select_from(BranchMessage).where(
                BranchMessage.active_answer_version_id.is_not(None)
            )
        )
        assert links == active == 1


def test_manual_model_is_used_once(client: TestClient) -> None:
    conversation = create_conversation(client)
    response = client.post(
        f"/api/v1/conversations/{conversation['id']}/messages",
        json={
            "content": "指定模型",
            "selection_mode": "USER_SELECTED",
            "model_key": "MODEL_C",
        },
    )
    assert response.status_code == 201
    assert response.json()["active_answer"]["model_key"] == "MODEL_C"


def test_invalid_model_selection_is_rejected(client: TestClient) -> None:
    conversation = create_conversation(client)
    response = client.post(
        f"/api/v1/conversations/{conversation['id']}/messages",
        json={
            "content": "错误模型",
            "selection_mode": "USER_SELECTED",
            "model_key": "MODEL_X",
        },
    )
    assert response.status_code == 422


def test_provider_failure_keeps_message_and_failed_answer() -> None:
    settings = Settings(
        environment="test",
        database_url="sqlite://",
    )
    app = create_app(settings, UnavailableModelProvider())
    Base.metadata.create_all(app.state.engine)
    with TestClient(app) as client:
        conversation = create_conversation(client)
        response = client.post(
            f"/api/v1/conversations/{conversation['id']}/messages",
            json={"content": "仍需保存", "selection_mode": "AUTO_ROUTE"},
        )
        assert response.status_code == 201
        assert response.json()["generation"]["status"] == "FAILED"
        assert response.json()["active_answer"] is None

    with app.state.session_factory() as session:
        message = session.scalar(select(UserMessage))
        answer = session.scalar(select(AssistantAnswerVersion))
        link = session.scalar(select(BranchMessage))
        assert message is not None and message.status == "GENERATION_FAILED"
        assert answer is not None and answer.status == "FAILED"
        assert link is not None and link.active_answer_version_id is None
    app.state.engine.dispose()


def test_message_list_uses_active_answer(client: TestClient) -> None:
    conversation = create_conversation(client)
    client.post(
        f"/api/v1/conversations/{conversation['id']}/messages",
        json={"content": "列表消息", "selection_mode": "AUTO_ROUTE"},
    )
    response = client.get(
        f"/api/v1/conversations/{conversation['id']}/messages"
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["active_answer"]["content"] == "Mock 回复：列表消息"
    assert body["items"][0]["active_answer"]["finish_reason"] == "stop"


def test_length_finish_reason_is_returned_immediately_and_in_history(
    client: TestClient, app
) -> None:
    def truncated_response(request):
        return ModelResult(
            content="未完成的回答",
            model_key=request.requested_model_key,
            model_id="truncated-model",
            input_tokens=10,
            output_tokens=4096,
            total_tokens=4106,
            finish_reason="length",
            provider_request_id="truncated-request",
        )

    app.state.providers.model._responder = truncated_response
    conversation = create_conversation(client)
    response = client.post(
        f"/api/v1/conversations/{conversation['id']}/messages",
        json={"content": "长回答", "selection_mode": "AUTO_ROUTE"},
    )

    assert response.status_code == 201
    assert response.json()["active_answer"]["finish_reason"] == "length"

    history = client.get(
        f"/api/v1/conversations/{conversation['id']}/messages"
    )
    assert history.status_code == 200
    assert history.json()["items"][0]["active_answer"]["finish_reason"] == "length"
