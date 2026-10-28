"""Extension point for future long-term memory retrieval.

The MVP intentionally does not provide a vector-store implementation.
"""

from __future__ import annotations

from typing import Protocol

from src.dialogue.models import TaskSnapshotRef


class MemoryRetriever(Protocol):
    async def search(self, session_id: str, query: str, limit: int = 5) -> list[TaskSnapshotRef]:
        """Return relevant historical task references without mutating dialogue state."""


class NoOpMemoryRetriever:
    async def search(self, session_id: str, query: str, limit: int = 5) -> list[TaskSnapshotRef]:
        return []
