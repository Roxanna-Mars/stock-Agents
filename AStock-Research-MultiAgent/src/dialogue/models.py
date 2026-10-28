"""Pydantic contracts for multi-turn research conversations.

The contracts deliberately separate the current utterance, the active research
task and the state mutation requested by that utterance.  This prevents an
intent label from being treated as an agent name and makes state transitions
auditable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IntentType(str, Enum):
    FACT_QUERY = "fact_query"
    METRIC_QUERY = "metric_query"
    FINANCIAL_CALCULATION = "financial_calculation"
    SINGLE_STOCK_ANALYSIS = "single_stock_analysis"
    MULTI_STOCK_COMPARISON = "multi_stock_comparison"
    REPORT_GENERATION = "report_generation"
    COMPREHENSIVE_RESEARCH = "comprehensive_research"
    OTHER = "other"


class IntentChange(str, Enum):
    NEW = "new"
    CONTINUE = "continue"
    REFINE = "refine"
    SWITCH = "switch"
    CANCEL = "cancel"
    RESUME = "resume"


class AnalysisDimension(str, Enum):
    FUNDAMENTAL = "fundamental"
    TECHNICAL = "technical"
    VALUE = "value"
    NEWS = "news"


class UpdateOperation(str, Enum):
    RETAIN = "retain"
    REPLACE = "replace"
    APPEND = "append"
    CLEAR = "clear"


class StockRef(StrictModel):
    name: str | None = None
    code: str | None = None
    market: str | None = None

    @model_validator(mode="after")
    def require_identity(self) -> "StockRef":
        if not (self.name or self.code):
            raise ValueError("a stock requires a name or code")
        return self


class StockPatch(StrictModel):
    operation: UpdateOperation = UpdateOperation.RETAIN
    value: list[StockRef] | None = None

    @model_validator(mode="after")
    def validate_value(self) -> "StockPatch":
        _validate_patch(self.operation, self.value)
        return self


class DimensionPatch(StrictModel):
    operation: UpdateOperation = UpdateOperation.RETAIN
    value: list[AnalysisDimension] | None = None

    @model_validator(mode="after")
    def validate_value(self) -> "DimensionPatch":
        _validate_patch(self.operation, self.value)
        return self


class TimeRangePatch(StrictModel):
    operation: UpdateOperation = UpdateOperation.RETAIN
    value: str | None = None

    @model_validator(mode="after")
    def validate_value(self) -> "TimeRangePatch":
        _validate_patch(self.operation, self.value)
        return self


class ConstraintPatch(StrictModel):
    operation: UpdateOperation = UpdateOperation.RETAIN
    value: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_value(self) -> "ConstraintPatch":
        _validate_patch(self.operation, self.value)
        return self


def _validate_patch(operation: UpdateOperation, value: Any) -> None:
    if operation in {UpdateOperation.RETAIN, UpdateOperation.CLEAR} and value is not None:
        raise ValueError(f"{operation.value} must not carry a value")
    if operation in {UpdateOperation.REPLACE, UpdateOperation.APPEND} and value is None:
        raise ValueError(f"{operation.value} requires a value")


class TaskStatePatch(StrictModel):
    tickers: StockPatch = Field(default_factory=StockPatch)
    analysis_dimensions: DimensionPatch = Field(default_factory=DimensionPatch)
    time_range: TimeRangePatch = Field(default_factory=TimeRangePatch)
    constraints: ConstraintPatch = Field(default_factory=ConstraintPatch)


class ContextualIntentResult(StrictModel):
    utterance_intent: IntentType
    intent_change: IntentChange
    state_patch: TaskStatePatch = Field(default_factory=TaskStatePatch)
    referenced_task_id: str | None = None
    requires_clarification: bool = False
    clarification_question: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    summary: str = ""
    source: Literal["llm", "deterministic_fallback"] = "deterministic_fallback"
    fallback_reason: str | None = None

    @model_validator(mode="after")
    def require_question(self) -> "ContextualIntentResult":
        if self.requires_clarification and not self.clarification_question:
            raise ValueError("clarification_question is required")
        return self


class PendingClarification(StrictModel):
    question: str
    source_query: str
    proposed_intent: ContextualIntentResult


class AnalysisResultRef(StrictModel):
    task_id: str
    execution_id: str | None = None
    dimensions: list[AnalysisDimension] = Field(default_factory=list)
    tickers: list[StockRef] = Field(default_factory=list)
    scope_hash: str
    data_as_of: str | None = None
    report_path: str | None = None


class TaskSnapshotRef(StrictModel):
    task_id: str
    overall_intent: IntentType | None = None
    tickers: list[StockRef] = Field(default_factory=list)
    analysis_dimensions: list[AnalysisDimension] = Field(default_factory=list)
    time_range: str | None = None
    constraints: dict[str, Any] = Field(default_factory=dict)
    result_refs: list[AnalysisResultRef] = Field(default_factory=list)
    status: str = "completed"
    summary: str = ""


class DialogueTaskState(StrictModel):
    session_id: str
    active_task_id: str | None = None
    last_utterance_intent: IntentType | None = None
    last_intent_change: IntentChange | None = None
    overall_task_intent: IntentType | None = None
    task_status: Literal[
        "idle", "active", "awaiting_clarification", "cancelled", "completed"
    ] = "idle"
    tickers: list[StockRef] = Field(default_factory=list)
    analysis_dimensions: list[AnalysisDimension] = Field(default_factory=list)
    time_range: str | None = None
    constraints: dict[str, Any] = Field(default_factory=dict)
    pending_clarification: PendingClarification | None = None
    task_history: list[TaskSnapshotRef] = Field(default_factory=list)
    result_refs: list[AnalysisResultRef] = Field(default_factory=list)
    state_version: int = 0
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DialogueResolution(StrictModel):
    turn_intent: ContextualIntentResult
    state: DialogueTaskState
    resolved_query: str
    selected_agents: list[
        Literal["fundamental", "technical", "value", "news", "comparison"]
    ] = Field(default_factory=list)
    should_execute: bool = True
    response_message: str | None = None
