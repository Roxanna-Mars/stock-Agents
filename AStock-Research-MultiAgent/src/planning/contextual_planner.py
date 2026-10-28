"""Translate durable dialogue state into one execution plan."""

from __future__ import annotations

from src.dialogue.models import (
    AnalysisDimension,
    ContextualIntentResult,
    DialogueResolution,
    DialogueTaskState,
    IntentChange,
    IntentType,
)


DIMENSION_TO_AGENT = {
    AnalysisDimension.FUNDAMENTAL: "fundamental",
    AnalysisDimension.TECHNICAL: "technical",
    AnalysisDimension.VALUE: "value",
    AnalysisDimension.NEWS: "news",
}

DIMENSION_LABEL = {
    AnalysisDimension.FUNDAMENTAL: "基本面",
    AnalysisDimension.TECHNICAL: "技术面",
    AnalysisDimension.VALUE: "估值",
    AnalysisDimension.NEWS: "新闻舆情",
}


def plan_contextual_turn(
    query: str,
    turn: ContextualIntentResult,
    state: DialogueTaskState,
) -> DialogueResolution:
    if state.task_status == "awaiting_clarification":
        question = (
            state.pending_clarification.question
            if state.pending_clarification
            else "请补充任务所需的信息。"
        )
        return DialogueResolution(
            turn_intent=turn,
            state=state,
            resolved_query=query,
            should_execute=False,
            response_message=question,
        )
    if turn.intent_change == IntentChange.CANCEL:
        return DialogueResolution(
            turn_intent=turn,
            state=state,
            resolved_query=query,
            should_execute=False,
            response_message="已取消当前投研任务。你可以开始新的研究任务，或恢复之前的任务。",
        )

    if state.overall_task_intent in {IntentType.FACT_QUERY, IntentType.METRIC_QUERY}:
        selected_agents = []
    elif state.overall_task_intent == IntentType.MULTI_STOCK_COMPARISON:
        selected_agents = ["comparison"]
    else:
        dimensions = list(state.analysis_dimensions)
        if not dimensions and state.overall_task_intent not in {
            IntentType.FACT_QUERY,
            IntentType.METRIC_QUERY,
        }:
            dimensions = list(AnalysisDimension)
        selected_agents = [DIMENSION_TO_AGENT[item] for item in dimensions]

    stock_text = "、".join(
        _stock_query_text(stock.name, stock.code) for stock in state.tickers
    )
    dimension_text = "、".join(
        DIMENSION_LABEL[item] for item in state.analysis_dimensions
    )
    suffix: list[str] = []
    if stock_text:
        suffix.append(f"研究对象：{stock_text}")
    if dimension_text:
        suffix.append(f"分析维度：{dimension_text}")
    if state.time_range:
        suffix.append(f"时间范围：{state.time_range}")
    resolved_query = query.strip()
    if suffix:
        resolved_query = f"{resolved_query}。{'；'.join(suffix)}"
    return DialogueResolution(
        turn_intent=turn,
        state=state,
        resolved_query=resolved_query,
        selected_agents=selected_agents,
        should_execute=True,
    )


def _stock_query_text(name: str | None, code: str | None) -> str:
    raw_code = (code or "").split(".")[-1]
    if name and raw_code:
        return f"{name}({raw_code})"
    return name or raw_code or "未知股票"
