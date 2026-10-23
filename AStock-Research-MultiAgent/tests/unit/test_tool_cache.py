from src.tools.tool_cache import (
    clear_tool_cache,
    get_cached_result,
    set_cached_result,
)


def test_cache_returns_value_until_ttl_expires(monkeypatch):
    clear_tool_cache()
    monkeypatch.setenv("MCP_CACHE_ENABLED", "1")
    monkeypatch.setenv("MCP_CACHE_TTL_SECONDS", "10")
    set_cached_result("key", {"value": 1}, now=100)

    assert get_cached_result("key", now=105) == (True, {"value": 1})
    assert get_cached_result("key", now=111) == (False, None)


def test_cache_can_be_disabled(monkeypatch):
    clear_tool_cache()
    monkeypatch.setenv("MCP_CACHE_ENABLED", "0")
    set_cached_result("key", "value", now=100)

    assert get_cached_result("key", now=101) == (False, None)
