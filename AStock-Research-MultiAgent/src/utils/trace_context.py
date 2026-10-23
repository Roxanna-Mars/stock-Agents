"""Async-safe context for attributing shared MCP calls to an agent."""

from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import json
from typing import Any, Iterator


_agent_name: ContextVar[str] = ContextVar("tool_trace_agent_name", default="unknown")
_seen_calls: ContextVar[set[str] | None] = ContextVar(
    "tool_trace_seen_calls",
    default=None,
)


def current_agent_name() -> str:
    return _agent_name.get()


def tool_call_fingerprint(tool_name: str, arguments: dict[str, Any]) -> str:
    canonical = json.dumps(
        arguments,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(f"{tool_name}:{canonical}".encode("utf-8")).hexdigest()


def mark_tool_call(fingerprint: str) -> bool:
    """Record a call and return whether it was already seen in this agent run."""
    seen = _seen_calls.get()
    if seen is None:
        seen = set()
        _seen_calls.set(seen)
    duplicate = fingerprint in seen
    seen.add(fingerprint)
    return duplicate


@contextmanager
def bind_agent_trace(agent_name: str) -> Iterator[None]:
    """Bind tool calls in the current async context to one agent execution."""
    agent_token = _agent_name.set(agent_name)
    calls_token = _seen_calls.set(set())
    try:
        yield
    finally:
        _seen_calls.reset(calls_token)
        _agent_name.reset(agent_token)
