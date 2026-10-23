"""Small process-local TTL cache for successful MCP tool results."""

from __future__ import annotations

from dataclasses import dataclass
import os
import time
from typing import Any


@dataclass(frozen=True)
class CacheEntry:
    created_at: float
    value: Any


_cache: dict[str, CacheEntry] = {}


def cache_enabled() -> bool:
    return os.getenv("MCP_CACHE_ENABLED", "1").strip().casefold() not in {
        "0",
        "false",
        "no",
        "off",
    }


def cache_ttl_seconds() -> float:
    try:
        return max(0.0, float(os.getenv("MCP_CACHE_TTL_SECONDS", "300")))
    except (TypeError, ValueError):
        return 300.0


def get_cached_result(key: str, now: float | None = None) -> tuple[bool, Any]:
    if not cache_enabled():
        return False, None
    entry = _cache.get(key)
    if entry is None:
        return False, None
    current_time = time.monotonic() if now is None else now
    if current_time - entry.created_at > cache_ttl_seconds():
        _cache.pop(key, None)
        return False, None
    return True, entry.value


def set_cached_result(key: str, value: Any, now: float | None = None) -> None:
    if cache_enabled():
        _cache[key] = CacheEntry(
            created_at=time.monotonic() if now is None else now,
            value=value,
        )


def clear_tool_cache() -> None:
    _cache.clear()
