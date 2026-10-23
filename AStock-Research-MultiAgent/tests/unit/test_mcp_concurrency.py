import asyncio

import pytest

from src.tools import mcp_client
from src.utils.trace_context import bind_agent_trace


class FakeTool:
    def __init__(self):
        self.name = "fake_tool"
        self.coroutine = self.call

    async def call(self, **arguments):
        return arguments


@pytest.mark.asyncio
async def test_parallel_initialization_happens_once(monkeypatch):
    mcp_client.clear_tool_cache()
    class FakeClient:
        get_tools_calls = 0

        def __init__(self, _configs):
            pass

        async def get_tools(self):
            type(self).get_tools_calls += 1
            await asyncio.sleep(0.01)
            return [FakeTool()]

    monkeypatch.setattr(mcp_client, "MultiServerMCPClient", FakeClient)
    monkeypatch.setattr(mcp_client, "_mcp_client_instance", None)
    monkeypatch.setattr(mcp_client, "_mcp_tools", None)
    monkeypatch.setattr(mcp_client, "_mcp_init_lock", asyncio.Lock())
    monkeypatch.setattr(mcp_client, "_mcp_tool_call_lock", asyncio.Lock())

    results = await asyncio.gather(*(
        mcp_client.get_mcp_tools()
        for _ in range(4)
    ))

    assert FakeClient.get_tools_calls == 1
    assert all(result is results[0] for result in results)


@pytest.mark.asyncio
async def test_wrapped_tool_calls_are_serialized(monkeypatch):
    mcp_client.clear_tool_cache()
    monkeypatch.setattr(mcp_client, "_mcp_tool_call_lock", asyncio.Lock())
    active_calls = 0
    maximum_active_calls = 0

    class ConcurrentProbeTool:
        name = "probe"

        def __init__(self):
            self.coroutine = self.call

        async def call(self, **arguments):
            nonlocal active_calls, maximum_active_calls
            active_calls += 1
            maximum_active_calls = max(maximum_active_calls, active_calls)
            await asyncio.sleep(0.01)
            active_calls -= 1
            return arguments

    tool = mcp_client._serialize_mcp_tool(ConcurrentProbeTool())

    results = await asyncio.gather(*(
        tool.coroutine(index=index)
        for index in range(4)
    ))

    assert maximum_active_calls == 1
    assert [result["index"] for result in results] == [0, 1, 2, 3]


@pytest.mark.asyncio
async def test_wrapped_tool_records_agent_timing_and_duplicates(monkeypatch):
    mcp_client.clear_tool_cache()
    monkeypatch.setattr(mcp_client, "_mcp_tool_call_lock", asyncio.Lock())
    records = []

    class TraceLogger:
        def log_tool_usage(self, **record):
            records.append(record)

    monkeypatch.setattr(
        mcp_client,
        "get_active_execution_logger",
        lambda: TraceLogger(),
    )
    tool = mcp_client._serialize_mcp_tool(FakeTool())

    with bind_agent_trace("technical_agent"):
        await tool.coroutine(code="sh.600519")
        await tool.coroutine(code="sh.600519")

    assert [record["agent_name"] for record in records] == [
        "technical_agent",
        "technical_agent",
    ]
    assert [record["duplicate_call"] for record in records] == [False, True]
    assert [record["cache_hit"] for record in records] == [False, True]
    assert all(record["success"] for record in records)
    assert all(record["queue_wait_seconds"] >= 0 for record in records)
