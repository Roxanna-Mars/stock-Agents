"""Core typed contracts for reproducible financial research runs.

The existing agents still exchange dictionaries.  These models form the stable
contract for the staged migration to typed data, calculation, claim, and audit
artifacts without forcing the current workflow to change all at once.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def utc_now() -> datetime:
    """Return an aware UTC timestamp so persisted runs are timezone-safe."""
    return datetime.now(timezone.utc)


def stable_content_hash(value: Any) -> str:
    """Create a stable SHA-256 hash for JSON-compatible provenance payloads."""
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class StrictModel(BaseModel):
    """Reject unknown fields to prevent silent contract drift."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Market(str, Enum):
    AUTO = "auto"
    CN = "cn"
    US = "us"
    HK = "hk"
    GLOBAL = "global"


class TaskType(str, Enum):
    COMPREHENSIVE_ANALYSIS = "comprehensive_analysis"
    FOCUSED_ANALYSIS = "focused_analysis"
    FINANCIAL_CALCULATION = "financial_calculation"
    MULTI_STOCK_COMPARISON = "multi_stock_comparison"
    EQUITY_RESEARCH = "equity_research"
    VALUATION = "valuation"
    EARNINGS_REVIEW = "earnings_review"
    IC_MEMO = "ic_memo"


class ArtifactKind(str, Enum):
    EVIDENCE = "evidence"
    DATA = "data"
    CALCULATION = "calculation"
    CLAIM = "claim"
    REPORT = "report"


class AuditSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class AuditStatus(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


class ResearchRequest(StrictModel):
    query: str = Field(min_length=1)
    symbols: list[str] = Field(default_factory=list)
    market: Market = Market.AUTO
    as_of: date
    task_type: TaskType = TaskType.COMPREHENSIVE_ANALYSIS
    horizon: str | None = None
    risk_profile: str | None = None
    output_format: Literal["markdown", "json", "html"] = "markdown"
    language: str = "zh-CN"

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query must not be blank")
        return value

    @field_validator("symbols")
    @classmethod
    def normalize_symbols(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            symbol = value.strip()
            if symbol and symbol not in seen:
                normalized.append(symbol)
                seen.add(symbol)
        return normalized


class DataRequirement(StrictModel):
    requirement_id: str = Field(min_length=1)
    data_type: str = Field(min_length=1)
    symbol: str | None = None
    provider_preferences: list[str] = Field(default_factory=list)
    required_fields: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    required: bool = True


class PlanBudget(StrictModel):
    max_tool_calls: int = Field(default=30, ge=1)
    max_llm_calls: int = Field(default=20, ge=1)
    max_debate_rounds: int = Field(default=1, ge=0, le=5)
    timeout_seconds: float = Field(default=900.0, gt=0)


class PlanStep(StrictModel):
    step_id: str = Field(min_length=1)
    role: str = Field(min_length=1)
    action: str = Field(min_length=1)
    depends_on: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    calculator: str | None = None
    required: bool = True


class ResearchPlan(StrictModel):
    plan_id: str = Field(min_length=1)
    request: ResearchRequest
    playbook_id: str = Field(min_length=1)
    data_requirements: list[DataRequirement] = Field(default_factory=list)
    steps: list[PlanStep] = Field(default_factory=list)
    budget: PlanBudget = Field(default_factory=PlanBudget)
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_step_graph(self) -> "ResearchPlan":
        step_ids = [step.step_id for step in self.steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("plan step_id values must be unique")
        known = set(step_ids)
        for step in self.steps:
            missing = set(step.depends_on) - known
            if missing:
                raise ValueError(
                    f"step {step.step_id!r} depends on unknown steps: {sorted(missing)}"
                )
            if step.step_id in step.depends_on:
                raise ValueError(f"step {step.step_id!r} cannot depend on itself")

        dependencies = {step.step_id: step.depends_on for step in self.steps}
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(step_id: str) -> None:
            if step_id in visiting:
                raise ValueError(f"plan contains a dependency cycle at {step_id!r}")
            if step_id in visited:
                return
            visiting.add(step_id)
            for dependency in dependencies[step_id]:
                visit(dependency)
            visiting.remove(step_id)
            visited.add(step_id)

        for step_id in step_ids:
            visit(step_id)
        return self


class ProvenanceRef(StrictModel):
    record_id: str = Field(min_length=1)
    kind: ArtifactKind
    relation: str = "supports"


class EvidenceRecord(StrictModel):
    evidence_id: str = Field(min_length=1)
    agent_name: str = Field(min_length=1)
    tool_name: str | None = None
    tool_call_id: str = ""
    arguments: dict[str, Any] = Field(default_factory=dict)
    content: str = ""
    content_truncated: bool = False
    success: bool = True
    error_type: str | None = None
    content_hash: str
    recorded_at: datetime = Field(default_factory=utc_now)

    @classmethod
    def create(
        cls,
        *,
        evidence_id: str,
        agent_name: str,
        tool_name: str | None,
        tool_call_id: str,
        arguments: dict[str, Any],
        content: str,
        stored_content: str | None = None,
        success: bool,
        error_type: str | None,
    ) -> "EvidenceRecord":
        stored = content if stored_content is None else stored_content
        return cls(
            evidence_id=evidence_id,
            agent_name=agent_name,
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            arguments=arguments,
            content=stored,
            content_truncated=len(stored) < len(content),
            success=success,
            error_type=error_type,
            content_hash=stable_content_hash(content),
        )

    def to_legacy_dict(self) -> dict[str, Any]:
        """Return the exact dictionary contract consumed by current agents/tests."""
        return {
            "evidence_id": self.evidence_id,
            "agent_name": self.agent_name,
            "tool_name": self.tool_name,
            "tool_call_id": self.tool_call_id,
            "arguments": self.arguments,
            "content": self.content,
            "content_truncated": self.content_truncated,
            "success": self.success,
            "error_type": self.error_type,
        }


class DataArtifact(StrictModel):
    artifact_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    data_type: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    as_of: date
    payload: dict[str, Any]
    source_url: str | None = None
    period_end: date | None = None
    published_at: datetime | None = None
    fetched_at: datetime = Field(default_factory=utc_now)
    currency: str | None = None
    unit: str | None = None
    payload_hash: str
    from_cache: bool = False
    stale: bool = False
    warnings: list[str] = Field(default_factory=list)

    @classmethod
    def create(cls, **values: Any) -> "DataArtifact":
        values.setdefault("payload_hash", stable_content_hash(values.get("payload", {})))
        return cls(**values)

    @property
    def is_point_in_time_safe(self) -> bool:
        if self.published_at is None:
            return True
        return self.published_at.date() <= self.as_of


class CalculationArtifact(StrictModel):
    calculation_id: str = Field(min_length=1)
    operator: str = Field(min_length=1)
    operator_version: str = Field(min_length=1)
    input_refs: list[str] = Field(default_factory=list)
    assumptions: dict[str, Any] = Field(default_factory=dict)
    formula: str = Field(min_length=1)
    result: dict[str, Any]
    currency: str | None = None
    unit: str | None = None
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    result_hash: str

    @classmethod
    def create(cls, **values: Any) -> "CalculationArtifact":
        values.setdefault("result_hash", stable_content_hash(values.get("result", {})))
        return cls(**values)


class Claim(StrictModel):
    claim_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    claim_type: Literal["numeric", "factual", "interpretive"]
    metric: str | None = None
    value: float | int | str | None = None
    unit: str | None = None
    period: str | None = None
    references: list[str] = Field(default_factory=list)


class AuditFinding(StrictModel):
    finding_id: str = Field(min_length=1)
    check_name: str = Field(min_length=1)
    severity: AuditSeverity
    status: AuditStatus
    message: str = Field(min_length=1)
    claim_id: str | None = None
    references: list[str] = Field(default_factory=list)
    expected: Any = None
    actual: Any = None


class ResearchArtifact(StrictModel):
    artifact_id: str = Field(min_length=1)
    request: ResearchRequest
    plan_id: str
    sections: dict[str, str] = Field(default_factory=dict)
    data_refs: list[str] = Field(default_factory=list)
    calculation_refs: list[str] = Field(default_factory=list)
    claim_refs: list[str] = Field(default_factory=list)
    audit_status: AuditStatus = AuditStatus.WARN
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
