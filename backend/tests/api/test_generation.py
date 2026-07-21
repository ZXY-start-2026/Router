from sqlalchemy import func, select

from app.db.models_generation import (
    ContextSnapshot,
    GenerationAttempt,
    GenerationTask,
    RouteCandidate,
    RouteSnapshot,
    SearchSnapshot,
)


def test_auto_route_persists_complete_generation_audit(client, app) -> None:
    conversation = client.post("/api/v1/conversations", json={}).json()
    response = client.post(
        f"/api/v1/conversations/{conversation['id']}/messages",
        json={"content": "audit", "selection_mode": "AUTO_ROUTE"},
    )
    assert response.status_code == 201
    generation = response.json()["generation"]
    assert generation["status"] == "SUCCEEDED"
    assert generation["search_status"] == "FAILED"
    assert generation["selected_model_key"] == "MODEL_A"

    details = client.get(f"/api/v1/generation-tasks/{generation['task_id']}")
    assert details.status_code == 200
    body = details.json()
    assert len(body["candidates"]) == 3
    assert [item["model_key"] for item in body["candidates"]] == [
        "MODEL_A",
        "MODEL_B",
        "MODEL_C",
    ]
    assert len(body["attempts"]) == 1
    assert body["attempts"][0]["status"] == "SUCCEEDED"

    with app.state.session_factory() as session:
        for entity in (
            SearchSnapshot,
            ContextSnapshot,
            GenerationTask,
            RouteSnapshot,
            GenerationAttempt,
        ):
            assert session.scalar(select(func.count()).select_from(entity)) == 1
        assert session.scalar(select(func.count()).select_from(RouteCandidate)) == 3
