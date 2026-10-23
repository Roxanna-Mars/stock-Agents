"""Rule-based failure attribution for benchmark results."""

from __future__ import annotations

from collections import Counter
from typing import Any


def attribute_failures(
    metrics: dict[str, Any], process_error: str | None
) -> list[str]:
    failures = []
    if process_error and "timeout" in process_error.casefold():
        failures.append("workflow_timeout")
    elif process_error:
        failures.append("process_error")
    if metrics.get("missing_agents"):
        failures.append("agent_incomplete")
    if not metrics.get("report_valid"):
        failures.append("report_incomplete")
    if metrics.get("missing_tool_groups"):
        failures.append("tool_omission")
    if metrics.get("forbidden_tools_selected"):
        failures.append("tool_misselection")
    if metrics.get("duplicate_tool_calls", 0):
        failures.append("duplicate_tool_call")
    if metrics.get("tool_failures", 0):
        failures.append("tool_execution_error")
    if (
        metrics.get("numeric_claims", 0)
        and metrics.get("numeric_evidence_grounding", 0) < 0.70
    ):
        failures.append("evidence_gap")
    if metrics.get("evidence_records", 0) and not metrics.get("evidence_references", 0):
        failures.append("missing_evidence_citations")
    elif metrics.get("evidence_references", 0) and metrics.get(
        "evidence_reference_precision", 0
    ) < 1.0:
        failures.append("invalid_evidence_citation")
    return failures


def summarize_failures(results: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(
        failure
        for result in results
        for failure in result.get("failure_modes", [])
    )
    return dict(sorted(counts.items()))
