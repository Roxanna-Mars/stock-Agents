from datetime import date

import pytest

from src.data.base import DataQuery
from src.data.providers.callable_provider import CallableDataProvider
from src.data.providers.mcp_provider import MCPDataProvider, MCPToolRoute
from src.data.registry import DataAccessError, DataProviderRegistry


@pytest.mark.asyncio
async def test_registry_falls_back_to_next_capable_provider():
    calls = []

    async def failing_fetcher(query):
        calls.append("primary")
        raise RuntimeError("rate limited")

    def backup_fetcher(query):
        calls.append("backup")
        return {"payload": {"close": 1500.0}}

    registry = DataProviderRegistry(
        [
            CallableDataProvider(
                name="primary",
                supported_data_types={"market_price"},
                fetcher=failing_fetcher,
            ),
            CallableDataProvider(
                name="backup",
                supported_data_types={"market_price"},
                fetcher=backup_fetcher,
            ),
        ]
    )
    query = DataQuery(
        data_type="market_price",
        symbol="sh.600519",
        as_of=date(2026, 10, 24),
    )

    artifact = await registry.fetch(query, preferred_providers=["primary"])

    assert calls == ["primary", "backup"]
    assert artifact.provider == "backup"
    assert artifact.payload["close"] == 1500.0


@pytest.mark.asyncio
async def test_registry_rejects_look_ahead_data():
    provider = CallableDataProvider(
        name="future",
        supported_data_types={"financial_statements"},
        fetcher=lambda query: {
            "as_of": "2026-10-25",
            "payload": {"revenue": 1},
        },
    )
    registry = DataProviderRegistry([provider])
    query = DataQuery(
        data_type="financial_statements",
        symbol="sh.600519",
        as_of=date(2026, 10, 24),
    )

    with pytest.raises(DataAccessError, match="after the requested as_of date"):
        await registry.fetch(query)


@pytest.mark.asyncio
async def test_fetch_many_preserves_query_order():
    async def fetcher(query):
        return {"payload": {"symbol": query.symbol}}

    provider = CallableDataProvider(
        name="mock",
        supported_data_types={"market_price"},
        fetcher=fetcher,
    )
    registry = DataProviderRegistry([provider])
    queries = [
        DataQuery(data_type="market_price", symbol=symbol, as_of=date(2026, 10, 24))
        for symbol in ("sh.600519", "sz.000858")
    ]

    artifacts = await registry.fetch_many(queries)

    assert [artifact.symbol for artifact in artifacts] == [
        "sh.600519",
        "sz.000858",
    ]


@pytest.mark.asyncio
async def test_mcp_provider_normalizes_tool_result_without_real_server():
    class FakeTool:
        name = "get_stock_basic_info"

        async def ainvoke(self, arguments):
            return {"code": arguments["code"], "name": "贵州茅台"}

    async def load_tools():
        return [FakeTool()]

    provider = MCPDataProvider(
        tool_loader=load_tools,
        routes={"company_profile": MCPToolRoute("get_stock_basic_info")},
    )
    query = DataQuery(
        data_type="company_profile",
        symbol="sh.600519",
        as_of=date(2026, 10, 24),
    )

    artifact = await provider.fetch(query)

    assert artifact.provider == "a_share_mcp"
    assert artifact.payload == {"code": "sh.600519", "name": "贵州茅台"}
    assert artifact.artifact_id.startswith("D-MCP-")


@pytest.mark.asyncio
async def test_mcp_provider_classifies_tool_error():
    class FakeTool:
        name = "get_stock_basic_info"

        async def ainvoke(self, arguments):
            return "Error: could not connect"

    async def load_tools():
        return [FakeTool()]

    provider = MCPDataProvider(
        tool_loader=load_tools,
        routes={"company_profile": MCPToolRoute("get_stock_basic_info")},
    )
    query = DataQuery(
        data_type="company_profile",
        symbol="sh.600519",
        as_of=date(2026, 10, 24),
    )

    with pytest.raises(RuntimeError, match="network"):
        await provider.fetch(query)
