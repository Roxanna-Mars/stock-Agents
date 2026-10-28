import asyncio

import pytest

from src.utils.execution_logger import (
    finalize_execution_logger,
    get_active_execution_logger,
    initialize_execution_logger,
)


def test_execution_logger_emits_compact_runtime_events(tmp_path):
    events = []
    logger = initialize_execution_logger(tmp_path, event_sink=events.append)

    logger.log_agent_start("fundamental_agent", {"secret_prompt": "not streamed"})
    logger.log_tool_start(
        "fundamental_agent",
        "get_profit_data",
        {"code": "sh.600519"},
        call_id="call-1",
    )
    logger.log_tool_usage(
        "fundamental_agent",
        "get_profit_data",
        {"code": "sh.600519"},
        "net profit: 100",
        1.2,
        call_id="call-1",
    )
    logger.log_agent_complete("fundamental_agent", {}, 2.0, success=True)
    finalize_execution_logger(success=True)

    event_types = [event["type"] for event in events]
    assert event_types == [
        "workflow.started",
        "agent.started",
        "tool.started",
        "tool.completed",
        "agent.completed",
        "workflow.completed",
    ]
    assert events[3]["payload"]["output_summary"] == "net profit: 100"
    assert "secret_prompt" not in events[1]["payload"]


@pytest.mark.asyncio
async def test_execution_logger_is_isolated_per_async_task(tmp_path):
    async def create_logger(name: str):
        logger = initialize_execution_logger(tmp_path / name)
        await asyncio.sleep(0)
        assert get_active_execution_logger() is logger
        execution_id = logger.execution_id
        finalize_execution_logger()
        return execution_id

    first, second = await asyncio.gather(create_logger("first"), create_logger("second"))

    assert first != second
    assert get_active_execution_logger() is None
