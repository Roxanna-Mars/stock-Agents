"""Compare benchmark result payloads and calculate resume-ready deltas."""

from __future__ import annotations

from typing import Any


RATE_METRICS = (
    "task_success_rate",
    "workflow_success_rate",
    "report_valid_rate",
    "tool_selection_accuracy",
    "tool_success_rate",
    "evidence_grounding_rate",
    "numeric_evidence_grounding_rate",
    "data_consistency_rate",
)


def _percent_change(before: float, after: float) -> float | None:
    if before == 0:
        return None
    return (after - before) / before * 100


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


def compare_payloads(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    before = baseline.get("summary", {})
    after = candidate.get("summary", {})
    percentage_point_deltas = {}
    for key in RATE_METRICS:
        before_value = _optional_float(before.get(key, 0))
        after_value = _optional_float(after.get(key, 0))
        percentage_point_deltas[key] = (
            round((after_value - before_value) * 100, 2)
            if before_value is not None and after_value is not None
            else None
        )
    relative_changes = {}
    for key in (
        "average_duration_seconds",
        "p50_duration_seconds",
        "p95_duration_seconds",
        "average_tokens",
    ):
        change = _percent_change(float(before.get(key, 0)), float(after.get(key, 0)))
        relative_changes[key] = round(change, 2) if change is not None else None

    return {
        "baseline": baseline.get("architecture") or baseline.get("benchmark", "baseline"),
        "candidate": candidate.get("architecture") or candidate.get("benchmark", "candidate"),
        "baseline_summary": before,
        "candidate_summary": after,
        "percentage_point_deltas": percentage_point_deltas,
        "relative_changes_percent": relative_changes,
        "failure_count_deltas": {
            key: candidate.get("failure_summary", {}).get(key, 0)
            - baseline.get("failure_summary", {}).get(key, 0)
            for key in sorted(
                set(baseline.get("failure_summary", {}))
                | set(candidate.get("failure_summary", {}))
            )
        },
    }


def render_comparison_markdown(comparison: dict[str, Any]) -> str:
    before = comparison["baseline_summary"]
    after = comparison["candidate_summary"]
    deltas = comparison["percentage_point_deltas"]
    changes = comparison["relative_changes_percent"]
    rows = [
        "# Benchmark Comparison",
        "",
        f"Baseline: `{comparison['baseline']}`  ",
        f"Candidate: `{comparison['candidate']}`",
        "",
        "| Metric | Baseline | Candidate | Change |",
        "|---|---:|---:|---:|",
    ]
    for key in RATE_METRICS:
        before_value = _optional_float(before.get(key, 0))
        after_value = _optional_float(after.get(key, 0))
        delta = deltas[key]
        if before_value is None or after_value is None or delta is None:
            rows.append(f"| {key} | n/a | n/a | n/a |")
            continue
        rows.append(
            f"| {key} | {before_value:.2%} | "
            f"{after_value:.2%} | {delta:+.2f} pp |"
        )
    for key in ("average_duration_seconds", "p95_duration_seconds", "average_tokens"):
        change = changes[key]
        change_text = "n/a" if change is None else f"{change:+.2f}%"
        rows.append(
            f"| {key} | {float(before.get(key, 0)):.2f} | "
            f"{float(after.get(key, 0)):.2f} | {change_text} |"
        )
    return "\n".join(rows) + "\n"
