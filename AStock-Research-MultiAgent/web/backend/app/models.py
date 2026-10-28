"""HTTP and persistence schemas for the Web application."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TaskStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"


class IntentTaskType(str, Enum):
    FACT_QUERY = "fact_query"
    FINANCIAL_CALCULATION = "financial_calculation"
    SINGLE_STOCK_ANALYSIS = "single_stock_analysis"
    MULTI_STOCK_COMPARISON = "multi_stock_comparison"
    COMPREHENSIVE_RESEARCH = "comprehensive_research"


class IntentStock(APIModel):
    name: str | None = None
    code: str | None = None
    market: str | None = None


class IntentAnalysis(APIModel):
    task_type: IntentTaskType
    stocks: list[IntentStock] = Field(default_factory=list)
    dimensions: list[
        Literal["fundamental", "technical", "value", "news", "comparison"]
    ] = Field(default_factory=list)
    time_range: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    suggested_route: Literal["direct_tool", "specialist_agent", "multi_agent"]
    execution_route: Literal["direct_tool", "legacy_workflow"] = "legacy_workflow"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    summary: str = ""
    source: Literal[
        "llm", "deterministic_direct", "deterministic_fallback"
    ] = "deterministic_fallback"
    fallback_reason: str | None = None


class IntentRequest(APIModel):
    query: str = Field(min_length=1, max_length=4000)


class ChatRequest(APIModel):
    query: str = Field(min_length=1, max_length=4000)
    session_id: str | None = None
    architecture: Literal[
        "react_multi_agent", "fixed_workflow", "single_agent"
    ] = "react_multi_agent"


class ChatAccepted(APIModel):
    task_id: str
    session_id: str
    status: TaskStatus
    events_url: str
    reused: bool = False


class CreateSessionRequest(APIModel):
    title: str = Field(default="新建投研会话", min_length=1, max_length=80)


class MessageRecord(APIModel):
    id: str
    session_id: str
    role: Literal["user", "assistant", "system"]
    content: str
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskRecord(APIModel):
    id: str
    session_id: str
    query: str
    status: TaskStatus
    architecture: str
    intent: dict[str, Any] | None = None
    execution_id: str | None = None
    report: str | None = None
    report_path: str | None = None
    error: str | None = None
    warnings: list[str] = Field(default_factory=list)
    duration_seconds: float | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    cancel_requested_at: datetime | None = None
    cancelled_at: datetime | None = None
    cancel_reason: str | None = None


class SessionSummary(APIModel):
    id: str
    title: str
    status: str
    created_at: datetime
    updated_at: datetime
    last_message: str | None = None


class SessionDetail(APIModel):
    id: str
    title: str
    status: str
    created_at: datetime
    updated_at: datetime
    messages: list[MessageRecord]
    tasks: list[TaskRecord]


class HealthResponse(APIModel):
    status: Literal["ok"] = "ok"
    database: Literal["ok"] = "ok"
    model_configured: bool
    mcp_configured: bool
