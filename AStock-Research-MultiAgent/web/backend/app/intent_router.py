"""Independent structured intent parser with deterministic fallback."""

from __future__ import annotations

import asyncio
import json
import os

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.planning.query_planner import normalize_stock_code, plan_query
from web.backend.app.models import (
    IntentAnalysis,
    IntentStock,
    IntentTaskType,
)


class IntentRouter:
    def __init__(self, *, use_llm: bool = True, timeout_seconds: float = 30.0) -> None:
        self.use_llm = use_llm
        self.timeout_seconds = timeout_seconds

    async def parse(self, query: str) -> IntentAnalysis:
        fallback = self._deterministic(query)
        api_key = os.getenv("OPENAI_COMPATIBLE_API_KEY")
        base_url = os.getenv("OPENAI_COMPATIBLE_BASE_URL")
        model = os.getenv("OPENAI_COMPATIBLE_MODEL")
        if not self.use_llm:
            return fallback.model_copy(
                update={"fallback_reason": "LLM intent routing is disabled"}
            )
        if not all((api_key, base_url, model)):
            return fallback.model_copy(
                update={"fallback_reason": "Model API is not configured"}
            )

        try:
            schema = json.dumps(
                IntentAnalysis.model_json_schema(),
                ensure_ascii=False,
                separators=(",", ":"),
            )
            llm = ChatOpenAI(
                model=model,
                api_key=api_key,
                base_url=base_url,
                temperature=0,
                max_tokens=1200,
            )
            structured = llm.with_structured_output(
                IntentAnalysis,
                method="json_mode",
            )
            result = await asyncio.wait_for(
                structured.ainvoke(
                    [
                        SystemMessage(
                            content=(
                                "You are an intent router for a financial research system. "
                                "Return only the requested JSON structure. Identify task type, "
                                "security names/codes, research dimensions, time range and explicit "
                                "parameters. Use direct_tool only for a simple factual lookup, "
                                "specialist_agent for one research dimension or a calculation, and "
                                "multi_agent for comparison or comprehensive research. Keep summary "
                                "brief and do not reveal chain-of-thought. execution_route must remain "
                                "legacy_workflow because routing recommendations are observational in v1. "
                                "Use the exact enum values and required fields defined by this JSON Schema: "
                                f"{schema}"
                            )
                        ),
                        HumanMessage(content=query),
                    ]
                ),
                timeout=self.timeout_seconds,
            )
            if not isinstance(result, IntentAnalysis):
                result = IntentAnalysis.model_validate(result)
            normalized_stocks: list[IntentStock] = []
            for stock in result.stocks:
                raw_code = (stock.code or "").strip()
                code = normalize_stock_code(raw_code.split(".")[-1]) if raw_code else None
                market = code.split(".")[0] if code and "." in code else stock.market
                normalized_stocks.append(
                    IntentStock(name=stock.name, code=code, market=market)
                )
            return result.model_copy(
                update={
                    "source": "llm",
                    "fallback_reason": None,
                    "execution_route": "legacy_workflow",
                    "stocks": normalized_stocks,
                }
            )
        except Exception as error:
            return fallback.model_copy(
                update={
                    "fallback_reason": f"Structured intent parsing failed: {type(error).__name__}"
                }
            )

    @staticmethod
    def _deterministic(query: str) -> IntentAnalysis:
        plan = plan_query(query)
        plan_type = plan["task_type"]
        mapping = {
            "financial_calculation": IntentTaskType.FINANCIAL_CALCULATION,
            "multi_stock_comparison": IntentTaskType.MULTI_STOCK_COMPARISON,
            "focused_analysis": IntentTaskType.SINGLE_STOCK_ANALYSIS,
            "comprehensive_analysis": IntentTaskType.COMPREHENSIVE_RESEARCH,
        }
        task_type = mapping.get(plan_type, IntentTaskType.COMPREHENSIVE_RESEARCH)
        factual_markers = ("查询", "是多少", "是什么", "最新价格", "基本信息")
        if any(marker in query for marker in factual_markers) and len(
            plan.get("requested_dimensions", [])
        ) <= 1:
            task_type = IntentTaskType.FACT_QUERY

        if task_type == IntentTaskType.FACT_QUERY:
            suggested_route = "direct_tool"
        elif task_type in {
            IntentTaskType.FINANCIAL_CALCULATION,
            IntentTaskType.SINGLE_STOCK_ANALYSIS,
        }:
            suggested_route = "specialist_agent"
        else:
            suggested_route = "multi_agent"

        stocks = [
            IntentStock(
                name=item.get("company_name"),
                code=item.get("stock_code"),
                market=(item.get("stock_code") or "").split(".")[0] or None,
            )
            for item in plan.get("stocks", [])
        ]
        dimensions = list(plan.get("requested_dimensions", []))
        if plan_type == "multi_stock_comparison" and "comparison" not in dimensions:
            dimensions.append("comparison")
        return IntentAnalysis(
            task_type=task_type,
            stocks=stocks,
            dimensions=dimensions,
            suggested_route=suggested_route,
            execution_route="legacy_workflow",
            confidence=0.72 if stocks else 0.55,
            summary=f"Deterministic planner selected {plan_type}.",
            source="deterministic_fallback",
        )
