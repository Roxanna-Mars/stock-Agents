"""Adapter from existing LangChain-compatible MCP tools to DataArtifact."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from src.data.base import DataQuery
from src.domain.models import DataArtifact, stable_content_hash
from src.utils.tool_result_utils import classify_tool_error


ToolLoader = Callable[[], Awaitable[Iterable[Any]]]


@dataclass(frozen=True)
class MCPToolRoute:
    tool_name: str
    symbol_argument: str | None = "code"
    static_arguments: dict[str, Any] = field(default_factory=dict)


DEFAULT_A_SHARE_ROUTES = {
    "company_profile": MCPToolRoute("get_stock_basic_info"),
    "market_price": MCPToolRoute("get_historical_k_data"),
    "profitability": MCPToolRoute("get_profit_data"),
    "operations": MCPToolRoute("get_operation_data"),
    "growth": MCPToolRoute("get_growth_data"),
    "balance_sheet": MCPToolRoute("get_balance_data"),
    "cash_flow_statement": MCPToolRoute("get_cash_flow_data"),
    "dupont": MCPToolRoute("get_dupont_data"),
    "dividends": MCPToolRoute("get_dividend_data"),
    "company_news": MCPToolRoute("crawl_news", symbol_argument="query"),
}


class MCPDataProvider:
    """Use configured MCP routes while preserving existing client safeguards."""

    def __init__(
        self,
        *,
        tool_loader: ToolLoader | None = None,
        routes: dict[str, MCPToolRoute] | None = None,
        name: str = "a_share_mcp",
    ) -> None:
        if tool_loader is None:
            from src.tools.mcp_client import get_mcp_tools

            tool_loader = get_mcp_tools
        self.name = name
        self._tool_loader = tool_loader
        self._routes = dict(routes or DEFAULT_A_SHARE_ROUTES)
        self.supported_data_types = frozenset(self._routes)

    async def fetch(self, query: DataQuery) -> DataArtifact:
        route = self._routes[query.data_type]
        tools = {tool.name: tool for tool in await self._tool_loader()}
        try:
            tool = tools[route.tool_name]
        except KeyError as error:
            raise LookupError(f"MCP tool {route.tool_name!r} is unavailable") from error

        arguments = dict(route.static_arguments)
        arguments.update(query.parameters)
        if route.symbol_argument and query.symbol:
            arguments.setdefault(route.symbol_argument, query.symbol)

        if hasattr(tool, "ainvoke"):
            raw = await tool.ainvoke(arguments)
        elif getattr(tool, "coroutine", None) is not None:
            raw = await tool.coroutine(**arguments)
        else:
            raise TypeError(f"MCP tool {route.tool_name!r} has no async invocation method")

        error_type = classify_tool_error(raw)
        if error_type is not None:
            raise RuntimeError(f"MCP tool failed with {error_type}: {raw}")

        payload = dict(raw) if isinstance(raw, dict) else {"raw": str(raw)}
        fingerprint = stable_content_hash(
            {
                "provider": self.name,
                "tool": route.tool_name,
                "arguments": arguments,
                "result": payload,
            }
        )[:16].upper()
        symbol = query.symbol or "GLOBAL"
        return DataArtifact.create(
            artifact_id=f"D-MCP-{fingerprint}",
            symbol=symbol,
            data_type=query.data_type,
            provider=self.name,
            as_of=query.as_of,
            payload=payload,
            warnings=([] if query.symbol else ["query has no security symbol"]),
        )
