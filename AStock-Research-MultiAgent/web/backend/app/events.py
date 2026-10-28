"""In-process wakeups complement SQLite, which remains the SSE source of truth."""

from __future__ import annotations

import asyncio


class EventBroker:
    def __init__(self) -> None:
        self._signals: dict[str, asyncio.Event] = {}

    def _signal(self, task_id: str) -> asyncio.Event:
        return self._signals.setdefault(task_id, asyncio.Event())

    def publish(self, task_id: str) -> None:
        self._signal(task_id).set()

    async def wait(self, task_id: str, timeout: float = 15.0) -> bool:
        signal = self._signal(task_id)
        try:
            await asyncio.wait_for(signal.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False
        finally:
            signal.clear()

    def discard(self, task_id: str) -> None:
        self._signals.pop(task_id, None)
