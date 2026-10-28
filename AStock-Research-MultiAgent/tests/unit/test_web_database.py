import pytest

import sqlite3

from web.backend.app.database import Database


def test_dialogue_state_projection_is_versioned_and_session_scoped(tmp_path):
    database = Database(tmp_path / "dialogue.db")
    database.initialize()
    first = database.create_session()
    second = database.create_session()

    database.save_dialogue_state(
        first["id"],
        {
            "session_id": first["id"],
            "state_version": 1,
            "tickers": [{"code": "sh.600519"}],
        },
        expected_version=0,
    )

    assert database.get_dialogue_state(first["id"])["tickers"][0]["code"] == "sh.600519"
    assert database.get_dialogue_state(second["id"]) is None

    with pytest.raises(RuntimeError, match="concurrently"):
        database.save_dialogue_state(
            first["id"],
            {
                "session_id": first["id"],
                "state_version": 1,
            },
            expected_version=0,
        )


def test_database_persists_session_task_message_and_events(tmp_path):
    database = Database(tmp_path / "web.db")
    database.initialize()
    session = database.create_session()

    task, reused = database.create_task(
        session_id=session["id"],
        query="分析贵州茅台(600519)",
        architecture="react_multi_agent",
        idempotency_key="request-1",
    )
    duplicate, duplicate_reused = database.create_task(
        session_id=session["id"],
        query="不会被重复提交",
        architecture="react_multi_agent",
        idempotency_key="request-1",
    )
    event_id = database.append_event(
        task["id"], "agent.started", {"agent_name": "fundamental_agent"}
    )

    detail = database.get_session(session["id"])
    events = database.list_events(task["id"])

    assert reused is False
    assert duplicate_reused is True
    assert duplicate["id"] == task["id"]
    assert len(detail["messages"]) == 1
    assert len(detail["tasks"]) == 1
    assert events[0]["id"] == event_id
    assert events[0]["payload"]["agent_name"] == "fundamental_agent"


def test_database_recovers_interrupted_tasks(tmp_path):
    database = Database(tmp_path / "web.db")
    database.initialize()
    session = database.create_session()
    task, _ = database.create_task(
        session_id=session["id"],
        query="分析贵州茅台(600519)",
        architecture="react_multi_agent",
        idempotency_key=None,
    )

    assert database.recover_incomplete_tasks() == 1
    assert database.get_task(task["id"])["status"] == "failed"
    assert database.list_events(task["id"])[0]["event_type"] == "task.failed"


def test_database_recovers_cancelling_task_as_cancelled(tmp_path):
    database = Database(tmp_path / "cancel-recovery.db")
    database.initialize()
    session = database.create_session()
    task, _ = database.create_task(
        session_id=session["id"],
        query="分析贵州茅台(600519)",
        architecture="react_multi_agent",
        idempotency_key=None,
    )
    database.update_task(
        task["id"],
        status="cancelling",
        cancel_reason="Cancelled by user",
    )

    assert database.recover_incomplete_tasks() == 1
    recovered = database.get_task(task["id"])
    assert recovered["status"] == "cancelled"
    assert recovered["cancel_reason"] == "Cancelled by user"
    assert database.list_events(task["id"])[0]["event_type"] == "task.cancelled"


def test_database_adds_cancellation_columns_to_existing_schema(tmp_path):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE sessions (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE tasks (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                query TEXT NOT NULL,
                status TEXT NOT NULL,
                architecture TEXT NOT NULL,
                idempotency_key TEXT UNIQUE,
                intent_json TEXT,
                execution_id TEXT,
                report TEXT,
                report_path TEXT,
                error TEXT,
                warnings_json TEXT NOT NULL DEFAULT '[]',
                duration_seconds REAL,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT
            );
            """
        )

    database = Database(path)
    database.initialize()

    with database.connect() as connection:
        columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(tasks)")
        }
    assert {"cancel_requested_at", "cancelled_at", "cancel_reason"} <= columns
