"""Pure and deterministic dialogue-state transitions."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, TypeVar
from uuid import uuid4

from src.dialogue.models import (
    ContextualIntentResult,
    AnalysisResultRef,
    DialogueTaskState,
    IntentChange,
    PendingClarification,
    StockRef,
    TaskSnapshotRef,
    UpdateOperation,
)


T = TypeVar("T")


def _dedupe_stocks(values: list[StockRef]) -> list[StockRef]:
    result: list[StockRef] = []
    seen: set[str] = set()
    for stock in values:
        key = (stock.code or stock.name or "").casefold()
        if key and key not in seen:
            result.append(stock)
            seen.add(key)
    return result


def _apply_list_patch(current: list[T], operation: UpdateOperation, value: list[T] | None) -> list[T]:
    if operation == UpdateOperation.RETAIN:
        return list(current)
    if operation == UpdateOperation.CLEAR:
        return []
    if operation == UpdateOperation.REPLACE:
        return list(value or [])
    result = list(current)
    for item in value or []:
        if item not in result:
            result.append(item)
    return result


def _apply_scalar_patch(current: T | None, operation: UpdateOperation, value: T | None) -> T | None:
    if operation == UpdateOperation.RETAIN:
        return current
    if operation == UpdateOperation.CLEAR:
        return None
    return value


def _apply_mapping_patch(
    current: dict[str, Any], operation: UpdateOperation, value: dict[str, Any] | None
) -> dict[str, Any]:
    if operation == UpdateOperation.RETAIN:
        return dict(current)
    if operation == UpdateOperation.CLEAR:
        return {}
    if operation == UpdateOperation.REPLACE:
        return dict(value or {})
    return {**current, **(value or {})}


def _snapshot(state: DialogueTaskState, status: str | None = None) -> TaskSnapshotRef | None:
    if not state.active_task_id:
        return None
    return TaskSnapshotRef(
        task_id=state.active_task_id,
        overall_intent=state.overall_task_intent,
        tickers=state.tickers,
        analysis_dimensions=state.analysis_dimensions,
        time_range=state.time_range,
        constraints=state.constraints,
        result_refs=state.result_refs,
        status=status or state.task_status,
        summary=_task_summary(state),
    )


def _task_summary(state: DialogueTaskState) -> str:
    stocks = "、".join(stock.name or stock.code or "未知股票" for stock in state.tickers)
    dimensions = ", ".join(item.value for item in state.analysis_dimensions)
    return f"{stocks or '未指定股票'} / {dimensions or '未指定维度'}"


def apply_dialogue_turn(
    previous: DialogueTaskState,
    turn: ContextualIntentResult,
    *,
    query: str,
) -> DialogueTaskState:
    """Apply one validated turn without performing I/O or calling an LLM."""

    state = previous.model_copy(deep=True)
    history = list(state.task_history)

    if turn.intent_change == IntentChange.RESUME:
        if not history:
            return _clarification_state(
                state,
                turn,
                query,
                "当前会话没有可以恢复的历史投研任务。请说明你想研究的股票。",
            )
        snapshot = next(
            (
                item
                for item in reversed(history)
                if not turn.referenced_task_id or item.task_id == turn.referenced_task_id
            ),
            None,
        )
        if snapshot is None:
            return _clarification_state(
                state,
                turn,
                query,
                "没有找到指定的历史任务，请重新选择需要恢复的任务。",
            )
        state.active_task_id = snapshot.task_id
        state.overall_task_intent = snapshot.overall_intent
        state.tickers = list(snapshot.tickers)
        state.analysis_dimensions = list(snapshot.analysis_dimensions)
        state.time_range = snapshot.time_range
        state.constraints = dict(snapshot.constraints)
        state.result_refs = list(snapshot.result_refs)
        state.task_status = "active"

    elif turn.intent_change == IntentChange.CANCEL:
        snapshot = _snapshot(state, status="cancelled")
        if snapshot:
            history.append(snapshot)
        state.task_status = "cancelled"
        state.pending_clarification = None
        state.task_history = history[-20:]
        return _finalize(state, turn)

    elif turn.intent_change in {IntentChange.NEW, IntentChange.SWITCH}:
        snapshot = _snapshot(state)
        if snapshot:
            history.append(snapshot)
        state.active_task_id = str(uuid4())
        state.overall_task_intent = turn.utterance_intent
        state.task_status = "active"
        state.pending_clarification = None
        state.result_refs = []
        if turn.intent_change == IntentChange.SWITCH:
            state.tickers = []
            state.analysis_dimensions = []
            state.time_range = None
            state.constraints = {}

    else:
        if not state.active_task_id:
            state.active_task_id = str(uuid4())
        if state.overall_task_intent is None:
            state.overall_task_intent = turn.utterance_intent
        elif turn.utterance_intent != type(turn.utterance_intent).OTHER:
            state.overall_task_intent = turn.utterance_intent
        state.task_status = "active"
        state.pending_clarification = None

    patch = turn.state_patch
    state.tickers = _dedupe_stocks(
        _apply_list_patch(state.tickers, patch.tickers.operation, patch.tickers.value)
    )
    state.analysis_dimensions = _apply_list_patch(
        state.analysis_dimensions,
        patch.analysis_dimensions.operation,
        patch.analysis_dimensions.value,
    )
    state.time_range = _apply_scalar_patch(
        state.time_range, patch.time_range.operation, patch.time_range.value
    )
    state.constraints = _apply_mapping_patch(
        state.constraints, patch.constraints.operation, patch.constraints.value
    )
    state.task_history = history[-20:]

    if turn.requires_clarification:
        return _clarification_state(
            state,
            turn,
            query,
            turn.clarification_question or "请补充执行该任务所需的信息。",
        )
    if not state.tickers and turn.utterance_intent not in {
        type(turn.utterance_intent).OTHER,
        type(turn.utterance_intent).FACT_QUERY,
    }:
        return _clarification_state(
            state,
            turn,
            query,
            "请说明要研究的股票名称或代码。",
        )
    return _finalize(state, turn)


def _clarification_state(
    state: DialogueTaskState,
    turn: ContextualIntentResult,
    query: str,
    question: str,
) -> DialogueTaskState:
    state.task_status = "awaiting_clarification"
    state.pending_clarification = PendingClarification(
        question=question,
        source_query=query,
        proposed_intent=turn,
    )
    return _finalize(state, turn)


def _finalize(
    state: DialogueTaskState, turn: ContextualIntentResult
) -> DialogueTaskState:
    state.last_utterance_intent = turn.utterance_intent
    state.last_intent_change = turn.intent_change
    state.state_version += 1
    state.updated_at = datetime.now(timezone.utc)
    return DialogueTaskState.model_validate(state.model_dump())


def record_analysis_result(
    state: DialogueTaskState,
    *,
    execution_id: str | None,
    report_path: str | None,
) -> DialogueTaskState:
    """Attach a compact, scope-addressed result reference after execution."""
    updated = state.model_copy(deep=True)
    scope = {
        "tickers": [stock.model_dump(mode="json") for stock in updated.tickers],
        "dimensions": [item.value for item in updated.analysis_dimensions],
        "time_range": updated.time_range,
        "constraints": updated.constraints,
    }
    scope_hash = hashlib.sha256(
        json.dumps(scope, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    if updated.active_task_id:
        updated.result_refs = [
            *updated.result_refs,
            AnalysisResultRef(
                task_id=updated.active_task_id,
                execution_id=execution_id,
                dimensions=updated.analysis_dimensions,
                tickers=updated.tickers,
                scope_hash=scope_hash,
                data_as_of=datetime.now(timezone.utc).isoformat(),
                report_path=report_path,
            ),
        ][-20:]
    updated.task_status = "completed"
    updated.state_version += 1
    updated.updated_at = datetime.now(timezone.utc)
    return DialogueTaskState.model_validate(updated.model_dump())
