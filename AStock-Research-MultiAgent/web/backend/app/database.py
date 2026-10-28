"""Small SQLite repository for sessions, messages, tasks and replayable events."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


class Database:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = threading.RLock()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS tasks (
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
                    completed_at TEXT,
                    cancel_requested_at TEXT,
                    cancelled_at TEXT,
                    cancel_reason TEXT
                );

                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS dialogue_states (
                    session_id TEXT PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,
                    state_json TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_messages_session
                    ON messages(session_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_tasks_session
                    ON tasks(session_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_events_task
                    ON events(task_id, id);
                """
            )
            task_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(tasks)").fetchall()
            }
            for name, definition in (
                ("cancel_requested_at", "TEXT"),
                ("cancelled_at", "TEXT"),
                ("cancel_reason", "TEXT"),
            ):
                if name not in task_columns:
                    connection.execute(
                        f"ALTER TABLE tasks ADD COLUMN {name} {definition}"
                    )

    def healthcheck(self) -> None:
        with self.connect() as connection:
            connection.execute("SELECT 1").fetchone()

    def create_session(self, title: str = "新建投研会话") -> dict[str, Any]:
        session_id = str(uuid.uuid4())
        now = utc_now()
        with self._lock, self.connect() as connection:
            connection.execute(
                "INSERT INTO sessions(id, title, status, created_at, updated_at) "
                "VALUES (?, ?, 'active', ?, ?)",
                (session_id, title, now, now),
            )
        return self.get_session_row(session_id)

    def get_session_row(self, session_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
        if row is None:
            raise KeyError(session_id)
        return dict(row)

    def list_sessions(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT s.*,
                    (SELECT content FROM messages m
                     WHERE m.session_id = s.id
                     ORDER BY m.created_at DESC LIMIT 1) AS last_message
                FROM sessions s
                ORDER BY s.updated_at DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_session(self, session_id: str) -> dict[str, Any]:
        session = self.get_session_row(session_id)
        with self.connect() as connection:
            messages = connection.execute(
                "SELECT * FROM messages WHERE session_id = ? ORDER BY created_at, rowid",
                (session_id,),
            ).fetchall()
            tasks = connection.execute(
                "SELECT * FROM tasks WHERE session_id = ? ORDER BY created_at, rowid",
                (session_id,),
            ).fetchall()
        session["messages"] = [self._message_from_row(row) for row in messages]
        session["tasks"] = [self._task_from_row(row) for row in tasks]
        return session

    def list_recent_messages(
        self,
        session_id: str,
        *,
        limit: int = 6,
        exclude_task_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return a bounded chronological context window for intent parsing."""
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM messages WHERE session_id = ? "
                "ORDER BY created_at DESC, rowid DESC LIMIT ?",
                (session_id, limit + (1 if exclude_task_id else 0)),
            ).fetchall()
        messages = [self._message_from_row(row) for row in reversed(rows)]
        if exclude_task_id:
            messages = [
                item
                for item in messages
                if item.get("metadata", {}).get("task_id") != exclude_task_id
            ]
        return messages[-limit:]

    def get_dialogue_state(self, session_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT state_json FROM dialogue_states WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return json.loads(row["state_json"]) if row is not None else None

    def save_dialogue_state(
        self,
        session_id: str,
        state: dict[str, Any],
        *,
        expected_version: int,
    ) -> None:
        """Persist a state projection with optimistic version validation."""
        new_version = int(state.get("state_version", 0))
        if new_version != expected_version + 1:
            raise ValueError(
                f"invalid dialogue state version {new_version}; expected {expected_version + 1}"
            )
        with self._lock, self.connect() as connection:
            existing = connection.execute(
                "SELECT version FROM dialogue_states WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if existing is None:
                if expected_version != 0:
                    raise RuntimeError("dialogue state changed concurrently")
                connection.execute(
                    "INSERT INTO dialogue_states(session_id, state_json, version, updated_at) "
                    "VALUES (?, ?, ?, ?)",
                    (session_id, _json(state), new_version, utc_now()),
                )
                return
            if int(existing["version"]) != expected_version:
                raise RuntimeError("dialogue state changed concurrently")
            cursor = connection.execute(
                "UPDATE dialogue_states SET state_json = ?, version = ?, updated_at = ? "
                "WHERE session_id = ? AND version = ?",
                (_json(state), new_version, utc_now(), session_id, expected_version),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("dialogue state changed concurrently")

    def delete_session(self, session_id: str) -> bool:
        with self._lock, self.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM sessions WHERE id = ?", (session_id,)
            )
        return cursor.rowcount > 0

    def session_has_active_tasks(self, session_id: str) -> bool:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS total FROM tasks "
                "WHERE session_id = ? AND status IN ('queued', 'running', 'cancelling')",
                (session_id,),
            ).fetchone()
        return bool(row["total"])

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        message_id = str(uuid.uuid4())
        now = utc_now()
        with self._lock, self.connect() as connection:
            connection.execute(
                "INSERT INTO messages(id, session_id, role, content, metadata_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (message_id, session_id, role, content, _json(metadata or {}), now),
            )
            connection.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (now, session_id),
            )
        return {
            "id": message_id,
            "session_id": session_id,
            "role": role,
            "content": content,
            "metadata": metadata or {},
            "created_at": now,
        }

    def create_task(
        self,
        *,
        session_id: str,
        query: str,
        architecture: str,
        idempotency_key: str | None,
    ) -> tuple[dict[str, Any], bool]:
        with self._lock, self.connect() as connection:
            if idempotency_key:
                existing = connection.execute(
                    "SELECT * FROM tasks WHERE idempotency_key = ?",
                    (idempotency_key,),
                ).fetchone()
                if existing is not None:
                    return self._task_from_row(existing), True

            session = connection.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
            if session is None:
                raise KeyError(session_id)

            task_id = str(uuid.uuid4())
            message_id = str(uuid.uuid4())
            now = utc_now()
            connection.execute(
                """
                INSERT INTO tasks(
                    id, session_id, query, status, architecture,
                    idempotency_key, created_at
                ) VALUES (?, ?, ?, 'queued', ?, ?, ?)
                """,
                (task_id, session_id, query, architecture, idempotency_key, now),
            )
            connection.execute(
                "INSERT INTO messages(id, session_id, role, content, metadata_json, created_at) "
                "VALUES (?, ?, 'user', ?, ?, ?)",
                (message_id, session_id, query, _json({"task_id": task_id}), now),
            )
            title = session["title"]
            if title == "新建投研会话":
                title = query.strip().replace("\n", " ")[:32] or title
            connection.execute(
                "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
                (title, now, session_id),
            )
            row = connection.execute(
                "SELECT * FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
        return self._task_from_row(row), False

    def get_task(self, task_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
        if row is None:
            raise KeyError(task_id)
        return self._task_from_row(row)

    def get_task_by_idempotency_key(self, key: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM tasks WHERE idempotency_key = ?", (key,)
            ).fetchone()
        return self._task_from_row(row) if row is not None else None

    def update_task(self, task_id: str, **fields: Any) -> dict[str, Any]:
        allowed = {
            "status",
            "intent_json",
            "execution_id",
            "report",
            "report_path",
            "error",
            "warnings_json",
            "duration_seconds",
            "started_at",
            "completed_at",
            "cancel_requested_at",
            "cancelled_at",
            "cancel_reason",
        }
        invalid = set(fields) - allowed
        if invalid:
            raise ValueError(f"unsupported task fields: {sorted(invalid)}")
        if not fields:
            return self.get_task(task_id)
        assignments = ", ".join(f"{name} = ?" for name in fields)
        values = list(fields.values()) + [task_id]
        with self._lock, self.connect() as connection:
            connection.execute(
                f"UPDATE tasks SET {assignments} WHERE id = ?", values
            )
            row = connection.execute(
                "SELECT * FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            if row is None:
                raise KeyError(task_id)
            connection.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (utc_now(), row["session_id"]),
            )
        return self._task_from_row(row)

    def update_task_if_status(
        self,
        task_id: str,
        expected_statuses: set[str],
        **fields: Any,
    ) -> tuple[dict[str, Any], bool]:
        """Atomically update a task only while it is in an expected state."""
        if not expected_statuses:
            raise ValueError("expected_statuses must not be empty")
        allowed = {
            "status",
            "intent_json",
            "execution_id",
            "report",
            "report_path",
            "error",
            "warnings_json",
            "duration_seconds",
            "started_at",
            "completed_at",
            "cancel_requested_at",
            "cancelled_at",
            "cancel_reason",
        }
        invalid = set(fields) - allowed
        if invalid:
            raise ValueError(f"unsupported task fields: {sorted(invalid)}")
        if not fields:
            return self.get_task(task_id), False

        assignments = ", ".join(f"{name} = ?" for name in fields)
        statuses = sorted(expected_statuses)
        placeholders = ", ".join("?" for _ in statuses)
        values = [*fields.values(), task_id, *statuses]
        with self._lock, self.connect() as connection:
            cursor = connection.execute(
                f"UPDATE tasks SET {assignments} "
                f"WHERE id = ? AND status IN ({placeholders})",
                values,
            )
            row = connection.execute(
                "SELECT * FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            if row is None:
                raise KeyError(task_id)
            if cursor.rowcount:
                connection.execute(
                    "UPDATE sessions SET updated_at = ? WHERE id = ?",
                    (utc_now(), row["session_id"]),
                )
        return self._task_from_row(row), cursor.rowcount == 1

    def append_event(
        self,
        task_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> int:
        with self._lock, self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO events(task_id, event_type, payload_json, created_at) "
                "VALUES (?, ?, ?, ?)",
                (task_id, event_type, _json(payload), utc_now()),
            )
        return int(cursor.lastrowid)

    def list_events(
        self,
        task_id: str,
        *,
        after_id: int = 0,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM events WHERE task_id = ? AND id > ? "
                "ORDER BY id LIMIT ?",
                (task_id, after_id, limit),
            ).fetchall()
        return [
            {
                "id": int(row["id"]),
                "task_id": row["task_id"],
                "event_type": row["event_type"],
                "payload": json.loads(row["payload_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def recover_incomplete_tasks(self) -> int:
        now = utc_now()
        with self._lock, self.connect() as connection:
            rows = connection.execute(
                "SELECT id, status FROM tasks "
                "WHERE status IN ('queued', 'running', 'cancelling')"
            ).fetchall()
            for row in rows:
                if row["status"] == "cancelling":
                    reason = "Cancellation completed during backend restart"
                    connection.execute(
                        "UPDATE tasks SET status = 'cancelled', cancel_reason = COALESCE(cancel_reason, ?), "
                        "cancelled_at = ?, completed_at = ? WHERE id = ?",
                        (reason, now, now, row["id"]),
                    )
                    connection.execute(
                        "INSERT INTO events(task_id, event_type, payload_json, created_at) "
                        "VALUES (?, 'task.cancelled', ?, ?)",
                        (
                            row["id"],
                            _json({"status": "cancelled", "reason": reason}),
                            now,
                        ),
                    )
                    continue
                message = "Backend restarted before the task completed"
                connection.execute(
                    "UPDATE tasks SET status = 'failed', error = ?, completed_at = ? "
                    "WHERE id = ?",
                    (message, now, row["id"]),
                )
                connection.execute(
                    "INSERT INTO events(task_id, event_type, payload_json, created_at) "
                    "VALUES (?, 'task.failed', ?, ?)",
                    (row["id"], _json({"error": message}), now),
                )
        return len(rows)

    @staticmethod
    def _message_from_row(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["metadata"] = json.loads(result.pop("metadata_json") or "{}")
        return result

    @staticmethod
    def _task_from_row(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["intent"] = json.loads(result.pop("intent_json") or "null")
        result["warnings"] = json.loads(result.pop("warnings_json") or "[]")
        result.pop("idempotency_key", None)
        return result
