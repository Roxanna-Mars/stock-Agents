import asyncio
import os

import pytest

from src.tools.mcp_client import close_mcp_client_sessions, get_mcp_tools


pytestmark = [pytest.mark.live_data, pytest.mark.asyncio]


async def test_parallel_stock_queries_return_valid_data():
    if os.getenv("RUN_LIVE_DATA") != "1":
        pytest.skip("set RUN_LIVE_DATA=1 to call the live Baostock MCP server")

    tools = await get_mcp_tools()
    stock_tool = next(
        (tool for tool in tools if tool.name == "get_stock_basic_info"),
        None,
    )
    assert stock_tool is not None, "get_stock_basic_info was not loaded"

    try:
        results = await asyncio.gather(*(
            stock_tool.ainvoke({"code": "sh.600519"})
            for _ in range(3)
        ))
    finally:
        await close_mcp_client_sessions()

    assert len(results) == 3
    for result in results:
        text = str(result)
        assert "Error:" not in text
        assert "10001001" not in text
        assert "sh.600519" in text
        assert "贵州茅台" in text
