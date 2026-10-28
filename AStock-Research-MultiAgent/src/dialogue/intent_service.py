"""Context-aware structured intent parsing with a safe deterministic fallback."""

from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.dialogue.models import (
    AnalysisDimension,
    ContextualIntentResult,
    DialogueTaskState,
    DimensionPatch,
    IntentChange,
    IntentType,
    StockPatch,
    StockRef,
    TaskStatePatch,
    UpdateOperation,
)
from src.planning.query_planner import extract_stocks, normalize_stock_code


DIMENSION_MARKERS: dict[AnalysisDimension, tuple[str, ...]] = {
    AnalysisDimension.FUNDAMENTAL: ("基本面", "财务", "营收", "利润", "ROE", "现金流"),
    AnalysisDimension.TECHNICAL: ("技术面", "走势", "均线", "MACD", "RSI"),
    AnalysisDimension.VALUE: ("估值", "市盈率", "市净率", "PE", "PB", "价值"),
    AnalysisDimension.NEWS: ("新闻", "舆情", "公告", "事件", "情绪"),
}


class ContextualIntentService:
    def __init__(self, *, use_llm: bool = True, timeout_seconds: float = 30.0) -> None:
        self.use_llm = use_llm
        self.timeout_seconds = timeout_seconds

    async def parse(
        self,
        query: str,
        previous: DialogueTaskState,
        recent_messages: list[dict[str, Any]] | None = None,
    ) -> ContextualIntentResult:
        fallback = self._deterministic(query, previous)
        api_key = os.getenv("OPENAI_COMPATIBLE_API_KEY")
        base_url = os.getenv("OPENAI_COMPATIBLE_BASE_URL")
        model = os.getenv("OPENAI_COMPATIBLE_MODEL")
        if not self.use_llm or not all((api_key, base_url, model)):
            reason = "LLM contextual routing is disabled or not configured"
            return fallback.model_copy(update={"fallback_reason": reason})

        schema = json.dumps(
            ContextualIntentResult.model_json_schema(),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        context = {
            "active_task": previous.model_dump(mode="json", exclude={"result_refs"}),
            "recent_messages": (recent_messages or [])[-6:],
            "current_user_utterance": query,
        }
        llm = ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=0,
            max_tokens=1800,
        )
        structured = llm.with_structured_output(
            ContextualIntentResult,
            method="json_mode",
        )
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                result = await asyncio.wait_for(
                    structured.ainvoke(
                        [
                            SystemMessage(content=self._system_prompt(schema, attempt, last_error)),
                            HumanMessage(content=json.dumps(context, ensure_ascii=False)),
                        ]
                    ),
                    timeout=self.timeout_seconds,
                )
                if not isinstance(result, ContextualIntentResult):
                    result = ContextualIntentResult.model_validate(result)
                return self._normalize(result).model_copy(
                    update={"source": "llm", "fallback_reason": None}
                )
            except Exception as error:  # validation and transport both fall back safely
                last_error = error
        return fallback.model_copy(
            update={
                "fallback_reason": (
                    "Structured contextual parsing failed: "
                    f"{type(last_error).__name__ if last_error else 'unknown'}"
                )
            }
        )

    @staticmethod
    def _system_prompt(schema: str, attempt: int, error: Exception | None) -> str:
        repair = ""
        if attempt and error:
            repair = f" Previous output failed validation ({type(error).__name__}); repair it."
        return (
            "You update the structured state of a Chinese stock-research conversation. "
            "Separate the current utterance intent from the overall task. Resolve pronouns only "
            "from supplied state. Use retain for an unmentioned field, replace for substitution, "
            "append for additions, and clear only for explicit reset. switch creates a new research "
            "scope; refine changes the active scope; cancel and resume must be explicit. Never invent "
            "a security code. Ask one concise clarification question when a required security or an "
            "execution-critical comparison dimension is ambiguous. You may propose a security-code "
            "candidate only when highly confident; a deterministic MCP lookup will verify it before "
            "execution. Do not reveal chain-of-thought. "
            f"Return only JSON matching this schema: {schema}.{repair}"
        )

    def _deterministic(
        self, query: str, previous: DialogueTaskState
    ) -> ContextualIntentResult:
        explicit_stocks = [
            StockRef(
                name=item.get("company_name"),
                code=item.get("stock_code"),
                market=(item.get("stock_code") or "").split(".")[0] or None,
            )
            for item in extract_stocks(query)
        ]
        dimensions = [
            dimension
            for dimension, markers in DIMENSION_MARKERS.items()
            if any(marker.casefold() in query.casefold() for marker in markers)
        ]
        is_cancel = any(marker in query for marker in ("取消", "算了", "停止这个任务")) and not any(
            marker in query for marker in ("换成", "改成", "改看")
        )
        is_switch = any(marker in query for marker in ("换成", "改成", "换一个"))
        is_resume = any(marker in query for marker in ("恢复", "继续之前", "回到之前"))
        is_comparison = any(marker in query for marker in ("比较", "对比", "相比"))

        if is_cancel:
            change = IntentChange.CANCEL
        elif is_resume:
            change = IntentChange.RESUME
        elif is_switch:
            change = IntentChange.SWITCH
        elif previous.active_task_id:
            change = IntentChange.REFINE if (dimensions or explicit_stocks or "只" in query) else IntentChange.CONTINUE
        else:
            change = IntentChange.NEW

        if is_comparison or len(explicit_stocks) > 1:
            intent = IntentType.MULTI_STOCK_COMPARISON
        elif any(marker in query for marker in ("多少", "是什么", "查询", "最新价格")):
            intent = IntentType.FACT_QUERY
        elif len(dimensions) == 1:
            intent = IntentType.SINGLE_STOCK_ANALYSIS
        else:
            intent = IntentType.COMPREHENSIVE_RESEARCH

        stock_operation = UpdateOperation.RETAIN
        stock_values: list[StockRef] | None = None
        if explicit_stocks:
            stock_operation = (
                UpdateOperation.APPEND
                if is_comparison and previous.tickers and not is_switch
                else UpdateOperation.REPLACE
            )
            stock_values = explicit_stocks
        dimension_operation = UpdateOperation.RETAIN
        dimension_values: list[AnalysisDimension] | None = None
        if dimensions:
            dimension_operation = UpdateOperation.REPLACE
            dimension_values = dimensions
        elif change == IntentChange.SWITCH:
            dimension_operation = UpdateOperation.CLEAR

        clarification = False
        question = None
        has_effective_stock = bool(explicit_stocks or previous.tickers)
        if not has_effective_stock and intent not in {IntentType.FACT_QUERY, IntentType.OTHER}:
            clarification = True
            question = "请说明要研究的股票名称或代码。"
        if is_comparison and len(explicit_stocks) + len(previous.tickers) < 2:
            clarification = True
            question = "请再提供一只需要比较的股票名称或代码。"

        return ContextualIntentResult(
            utterance_intent=intent,
            intent_change=change,
            state_patch=TaskStatePatch(
                tickers=StockPatch(operation=stock_operation, value=stock_values),
                analysis_dimensions=DimensionPatch(
                    operation=dimension_operation,
                    value=dimension_values,
                ),
            ),
            requires_clarification=clarification,
            clarification_question=question,
            confidence=0.78 if has_effective_stock else 0.45,
            summary="Deterministic context-aware fallback.",
            source="deterministic_fallback",
        )

    @staticmethod
    def _normalize(result: ContextualIntentResult) -> ContextualIntentResult:
        patch = result.state_patch.model_copy(deep=True)
        if patch.tickers.value:
            normalized: list[StockRef] = []
            for stock in patch.tickers.value:
                raw = (stock.code or "").strip()
                code = normalize_stock_code(raw.split(".")[-1]) if raw else None
                market = code.split(".")[0] if code and "." in code else stock.market
                normalized.append(stock.model_copy(update={"code": code, "market": market}))
            patch.tickers = patch.tickers.model_copy(update={"value": normalized})
        return result.model_copy(update={"state_patch": patch})
