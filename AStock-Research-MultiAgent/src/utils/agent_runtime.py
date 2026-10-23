"""Shared runtime limits for LLM and ReAct agent calls."""

from __future__ import annotations

import asyncio
import os
from typing import Awaitable, TypeVar


T = TypeVar("T")
DEFAULT_AGENT_TIMEOUT_SECONDS = 600.0


class AgentTimeoutError(TimeoutError):
    """Raised when one agent exceeds its configured runtime budget."""


def get_agent_timeout_seconds() -> float:
    """Read a positive timeout from the environment, falling back safely."""
    raw_value = os.getenv(
        "AGENT_TIMEOUT_SECONDS",
        str(int(DEFAULT_AGENT_TIMEOUT_SECONDS)),
    )
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        return DEFAULT_AGENT_TIMEOUT_SECONDS
    return value if value > 0 else DEFAULT_AGENT_TIMEOUT_SECONDS


async def invoke_with_timeout(
    awaitable: Awaitable[T],
    agent_name: str,
    timeout_seconds: float | None = None,
) -> T:
    """Await one agent call and convert asyncio's blank timeout into a useful error."""
    timeout = timeout_seconds or get_agent_timeout_seconds()
    try:
        return await asyncio.wait_for(awaitable, timeout=timeout)
    except asyncio.TimeoutError as exc:
        raise AgentTimeoutError(
            f"{agent_name} timed out after {timeout:g} seconds"
        ) from exc
