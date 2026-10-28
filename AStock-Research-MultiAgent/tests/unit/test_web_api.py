from fastapi.testclient import TestClient

from web.backend.app import main as api_module
from web.backend.app.database import Database
from web.backend.app.events import EventBroker
from web.backend.app.intent_router import IntentRouter


class FakeTaskManager:
    def __init__(self, database):
        self.database = database
        self.submitted = []

    def submit(self, task_id: str):
        self.submitted.append(task_id)

    def cancel(self, task_id: str):
        return self.database.update_task(
            task_id,
            status="cancelled",
            cancel_requested_at="2026-10-28T00:00:00+00:00",
            cancelled_at="2026-10-28T00:00:00+00:00",
            completed_at="2026-10-28T00:00:00+00:00",
            cancel_reason="Cancelled by user",
        )


def configure_test_app(monkeypatch, tmp_path):
    database = Database(tmp_path / "api.db")
    broker = EventBroker()
    manager = FakeTaskManager(database)
    monkeypatch.setattr(api_module, "database", database)
    monkeypatch.setattr(api_module, "broker", broker)
    monkeypatch.setattr(api_module, "task_manager", manager)
    monkeypatch.setattr(api_module, "intent_router", IntentRouter(use_llm=False))
    return database, manager


def test_chat_api_is_idempotent_and_session_is_restorable(monkeypatch, tmp_path):
    database, manager = configure_test_app(monkeypatch, tmp_path)

    with TestClient(api_module.app) as client:
        session = client.post("/api/sessions", json={"title": "茅台研究"}).json()
        headers = {"Idempotency-Key": "same-request"}
        body = {
            "query": "分析贵州茅台(600519)",
            "session_id": session["id"],
            "architecture": "react_multi_agent",
        }
        first = client.post("/api/chat", json=body, headers=headers)
        second = client.post("/api/chat", json=body, headers=headers)

        assert first.status_code == 202
        assert second.status_code == 202
        assert second.json()["reused"] is True
        assert second.json()["task_id"] == first.json()["task_id"]
        assert manager.submitted == [first.json()["task_id"]]

        restored = client.get(f"/api/sessions/{session['id']}")
        assert restored.status_code == 200
        assert restored.json()["messages"][0]["role"] == "user"
        assert len(restored.json()["tasks"]) == 1
        assert database.get_task(first.json()["task_id"])["status"] == "queued"


def test_sse_replays_persisted_events_and_finishes(monkeypatch, tmp_path):
    database, _ = configure_test_app(monkeypatch, tmp_path)

    with TestClient(api_module.app) as client:
        session = database.create_session()
        task, _ = database.create_task(
            session_id=session["id"],
            query="分析贵州茅台(600519)",
            architecture="react_multi_agent",
            idempotency_key=None,
        )
        database.append_event(task["id"], "agent.started", {"agent_name": "value_agent"})
        database.append_event(task["id"], "agent.completed", {"agent_name": "value_agent"})
        database.update_task(task["id"], status="completed")

        response = client.get(f"/api/chat/{task['id']}/events")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert "event: agent.started" in response.text
        assert "event: agent.completed" in response.text


def test_sse_replays_cancelled_event_and_finishes(monkeypatch, tmp_path):
    database, _ = configure_test_app(monkeypatch, tmp_path)

    with TestClient(api_module.app) as client:
        session = database.create_session()
        task, _ = database.create_task(
            session_id=session["id"],
            query="分析贵州茅台(600519)",
            architecture="react_multi_agent",
            idempotency_key=None,
        )
        database.append_event(
            task["id"],
            "task.cancelled",
            {"status": "cancelled", "reason": "Cancelled by user"},
        )
        database.update_task(task["id"], status="cancelled")

        response = client.get(f"/api/chat/{task['id']}/events")

        assert response.status_code == 200
        assert "event: task.cancelled" in response.text


def test_intent_endpoint_uses_safe_fallback(monkeypatch, tmp_path):
    configure_test_app(monkeypatch, tmp_path)

    with TestClient(api_module.app) as client:
        response = client.post(
            "/api/intent",
            json={"query": "查询贵州茅台(600519)基本信息"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["source"] == "deterministic_fallback"
        assert payload["execution_route"] == "legacy_workflow"


def test_cancel_task_endpoint_returns_cancelled_task(monkeypatch, tmp_path):
    database, _ = configure_test_app(monkeypatch, tmp_path)

    with TestClient(api_module.app) as client:
        session = database.create_session()
        task, _ = database.create_task(
            session_id=session["id"],
            query="分析贵州茅台(600519)",
            architecture="react_multi_agent",
            idempotency_key=None,
        )

        response = client.post(f"/api/tasks/{task['id']}/cancel")

        assert response.status_code == 202
        assert response.json()["status"] == "cancelled"
        assert response.json()["cancel_reason"] == "Cancelled by user"
