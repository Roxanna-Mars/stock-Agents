"""Deterministic validation for security identities proposed by an LLM."""

from __future__ import annotations

import re
from typing import Protocol

from src.dialogue.models import ContextualIntentResult, StockRef
from src.planning.query_planner import normalize_stock_code
from src.utils.tool_result_utils import classify_tool_error


CODE_PATTERN = re.compile(r"(?<!\d)(\d{6})(?!\d)")


class SecurityResolver(Protocol):
    async def validate(
        self,
        query: str,
        result: ContextualIntentResult,
    ) -> ContextualIntentResult:
        """Validate and normalize security identities in one intent result."""


class MCPSecurityResolver:
    """Verify model-proposed name/code pairs with the existing MCP tool.

    Codes explicitly typed by the user are treated as user parameters and only
    format-checked.  A code supplied only by the model must be confirmed by
    ``get_stock_basic_info`` before any research agent can run.
    """

    async def validate(
        self,
        query: str,
        result: ContextualIntentResult,
    ) -> ContextualIntentResult:
        patch = result.state_patch.model_copy(deep=True)
        stocks = patch.tickers.value
        if not stocks:
            return result
        explicit_codes = set(CODE_PATTERN.findall(query))
        verified: list[StockRef] = []
        for stock in stocks:
            raw = (stock.code or "").strip()
            if not raw:
                return self._clarify(
                    result,
                    f"请提供“{stock.name or '该股票'}”的六位股票代码，以便准确识别证券。",
                )
            digits = raw.split(".")[-1]
            if not CODE_PATTERN.fullmatch(digits):
                return self._clarify(result, f"股票代码“{raw}”格式不正确，请确认六位代码。")
            code = normalize_stock_code(digits)
            candidate = stock.model_copy(
                update={"code": code, "market": code.split(".")[0]}
            )
            if digits not in explicit_codes:
                if not await self._verify_candidate(candidate):
                    return self._clarify(
                        result,
                        f"无法验证“{stock.name or '该股票'}”与代码 {digits} 的对应关系，请确认股票代码。",
                    )
            verified.append(candidate)
        patch.tickers = patch.tickers.model_copy(update={"value": verified})
        return result.model_copy(update={"state_patch": patch})

    @staticmethod
    async def _verify_candidate(stock: StockRef) -> bool:
        from src.tools.mcp_client import get_mcp_tools

        tools = await get_mcp_tools()
        tool = next(
            (item for item in tools if getattr(item, "name", None) == "get_stock_basic_info"),
            None,
        )
        if tool is None:
            return False
        try:
            raw_result = await tool.ainvoke({"code": stock.code})
        except Exception:
            return False
        text = str(raw_result)
        if classify_tool_error(text) is not None:
            return False
        if not stock.name:
            return bool(stock.code and stock.code in text)
        expected = re.sub(r"\s+", "", stock.name).casefold()
        normalized_result = re.sub(r"\s+", "", text).casefold()
        return expected in normalized_result and bool(stock.code and stock.code in text)

    @staticmethod
    def _clarify(
        result: ContextualIntentResult,
        question: str,
    ) -> ContextualIntentResult:
        return result.model_copy(
            update={
                "requires_clarification": True,
                "clarification_question": question,
                "summary": "Security identity requires deterministic verification.",
            }
        )
