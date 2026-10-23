import asyncio

import pytest

from src.utils.agent_runtime import (
    AgentTimeoutError,
    DEFAULT_AGENT_TIMEOUT_SECONDS,
    get_agent_timeout_seconds,
    invoke_with_timeout,
)


def test_agent_timeout_configuration(monkeypatch):
    monkeypatch.setenv("AGENT_TIMEOUT_SECONDS", "12.5")
    assert get_agent_timeout_seconds() == 12.5

    monkeypatch.setenv("AGENT_TIMEOUT_SECONDS", "invalid")
    assert get_agent_timeout_seconds() == DEFAULT_AGENT_TIMEOUT_SECONDS

    monkeypatch.setenv("AGENT_TIMEOUT_SECONDS", "0")
    assert get_agent_timeout_seconds() == DEFAULT_AGENT_TIMEOUT_SECONDS


@pytest.mark.asyncio
async def test_invoke_timeout_has_actionable_error():
    async def slow_call():
        await asyncio.sleep(0.05)

    with pytest.raises(AgentTimeoutError, match="test_agent timed out"):
        await invoke_with_timeout(slow_call(), "test_agent", timeout_seconds=0.001)
