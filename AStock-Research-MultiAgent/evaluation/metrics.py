"""Deterministic metrics for financial-agent benchmark runs."""

from __future__ import annotations

import math
import hashlib
import json
import re
from statistics import mean
from typing import Any

from src.utils.evidence import evidence_reference_stats


NUMBER_PATTERN = re.compile(r"(?<![\d.])[-+]?\d[\d,]*(?:\.\d+)?%?")


def ratio(numerator: int | float, denominator: int | float) -> float:
    return float(numerator) / float(denominator) if denominator else 0.0


def percentile(values: list[float], percent: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * percent
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _normalized_numbers(text: str) -> set[str]:
    values = set()
    for match in NUMBER_PATTERN.findall(text):
        normalized = match.replace(",", "").lstrip("+")
        bare = normalized.rstrip("%")
        # Ignore section numbers and most years; focus on material numeric claims.
        if "." not in bare and "%" not in normalized and len(bare.lstrip("-")) < 4:
            continue
        values.add(normalized)
    return values


def numeric_evidence_grounding(report: str, tool_calls: list[dict[str, Any]]) -> dict[str, Any]:
    claims = _normalized_numbers(report)
    evidence_text = "\n".join(str(call.get("output", "")) for call in tool_calls)
    evidence = _normalized_numbers(evidence_text)
    supported = claims & evidence
    return {
        "numeric_claims": len(claims),
        "supported_numeric_claims": len(supported),
        "numeric_evidence_grounding": ratio(len(supported), len(claims)),
    }


def tool_output_signatures(tool_calls: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Keep privacy-safe hashes for consistency checks across repeated runs."""
    signatures = []
    for call in tool_calls:
        fingerprint = call.get("input_fingerprint")
        if not fingerprint:
            fallback = json.dumps(
                {
                    "tool": call.get("tool_name"),
                    "input": call.get("input", {}),
                },
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            )
            fingerprint = hashlib.sha256(fallback.encode("utf-8")).hexdigest()
        normalized_output = " ".join(str(call.get("output", "")).split())
        signatures.append(
            {
                "fingerprint": str(fingerprint),
                "output_hash": hashlib.sha256(
                    normalized_output.encode("utf-8")
                ).hexdigest(),
            }
        )
    return signatures


def expected_agents_for_architecture(
    case: dict[str, Any],
    architecture: str,
) -> set[str]:
    if architecture == "single_agent":
        return {"main", "single_agent", "summary_agent"}
    if architecture == "fixed_workflow":
        return {
            "main",
            "fundamental_agent",
            "technical_agent",
            "value_agent",
            "news_agent",
            "summary_agent",
        }
    return set(case.get("expected_agents", []))


def tool_selection_metrics(
    case: dict[str, Any], tool_calls: list[dict[str, Any]]
) -> dict[str, Any]:
    selected = [str(call.get("tool_name", "")) for call in tool_calls]
    selected_set = set(selected)
    groups = case.get("expected_tool_groups", [])
    group_hits = sum(bool(selected_set.intersection(group)) for group in groups)
    forbidden = set(case.get("forbidden_tools", []))
    forbidden_selected = sorted(selected_set & forbidden)
    denominator = len(groups) + (1 if forbidden else 0)
    score = group_hits + (1 if forbidden and not forbidden_selected else 0)
    duplicate_calls = sum(bool(call.get("duplicate_call")) for call in tool_calls)
    cache_hits = sum(bool(call.get("cache_hit")) for call in tool_calls)
    return {
        "selected_tools": selected,
        "expected_tool_groups": len(groups),
        "expected_tool_groups_hit": group_hits,
        "missing_tool_groups": [
            group for group in groups if not selected_set.intersection(group)
        ],
        "forbidden_tools_selected": forbidden_selected,
        "tool_selection_accuracy": ratio(score, denominator),
        "duplicate_tool_calls": duplicate_calls,
        "duplicate_tool_call_rate": ratio(duplicate_calls, len(tool_calls)),
        "cache_hits": cache_hits,
        "cache_hit_rate": ratio(cache_hits, len(tool_calls)),
    }


def score_case(
    case: dict[str, Any],
    artifacts: dict[str, Any],
    duration_seconds: float,
    return_code: int | None,
    process_error: str | None,
    architecture: str = "react_multi_agent",
) -> dict[str, Any]:
    report = artifacts["report"]
    tool_calls = artifacts["tool_calls"]
    agents = artifacts["agents"]
    info = artifacts["execution_info"]
    statuses = {name: data.get("status", "unknown") for name, data in agents.items()}
    expected_agents = expected_agents_for_architecture(case, architecture)
    completed_agents = {name for name, status in statuses.items() if status == "completed"}
    missing_agents = sorted(expected_agents - completed_agents)
    missing_terms = [term for term in case.get("required_terms", []) if term not in report]
    missing_companies = [name for name in case.get("companies", []) if name not in report]
    missing_codes = [code for code in case.get("stock_codes", []) if code not in report]

    selection = tool_selection_metrics(case, tool_calls)
    grounding = numeric_evidence_grounding(report, tool_calls)
    reference_grounding = evidence_reference_stats(
        report,
        artifacts.get("evidence_records", []),
    )
    tool_successes = sum(call.get("success") is True for call in tool_calls)
    tool_failures = len(tool_calls) - tool_successes
    queue_wait = sum(float(call.get("queue_wait_seconds", 0) or 0) for call in tool_calls)
    tool_execution = sum(
        float(call.get("execution_time_seconds", 0) or 0) for call in tool_calls
    )

    report_valid = bool(report) and not missing_terms and not missing_companies and not missing_codes
    task_success = (
        return_code == 0
        and process_error is None
        and bool(info.get("success"))
        and not missing_agents
        and report_valid
        and selection["tool_selection_accuracy"] == 1.0
    )
    return {
        "task_success": task_success,
        "architecture": architecture,
        "workflow_success": bool(info.get("success")),
        "report_valid": report_valid,
        "report_length": len(report),
        "missing_agents": missing_agents,
        "missing_terms": missing_terms,
        "missing_companies": missing_companies,
        "missing_stock_codes": missing_codes,
        "agent_statuses": statuses,
        "tool_calls": len(tool_calls),
        "tool_successes": tool_successes,
        "tool_failures": tool_failures,
        "tool_success_rate": ratio(tool_successes, len(tool_calls)),
        "tool_queue_wait_seconds": round(queue_wait, 3),
        "tool_execution_seconds": round(tool_execution, 3),
        "duration_seconds": round(duration_seconds, 3),
        "token_usage": artifacts["token_usage"],
        "tool_output_signatures": tool_output_signatures(tool_calls),
        **selection,
        **grounding,
        **reference_grounding,
    }


def aggregate_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    if not results:
        return {}
    metrics = [result["metrics"] for result in results]
    durations = [float(metric["duration_seconds"]) for metric in metrics]
    tokens = [int(metric["token_usage"].get("total_tokens", 0)) for metric in metrics]
    outputs_by_fingerprint: dict[str, list[str]] = {}
    for metric in metrics:
        for observation in metric.get("tool_output_signatures", []):
            outputs_by_fingerprint.setdefault(observation["fingerprint"], []).append(
                observation["output_hash"]
            )
    consistency_comparisons = 0
    consistent_pairs = 0
    for output_hashes in outputs_by_fingerprint.values():
        for index, output_hash in enumerate(output_hashes):
            for other_hash in output_hashes[index + 1:]:
                consistency_comparisons += 1
                consistent_pairs += output_hash == other_hash
    return {
        "total_runs": len(results),
        "task_success_rate": mean(bool(metric["task_success"]) for metric in metrics),
        "workflow_success_rate": mean(bool(metric["workflow_success"]) for metric in metrics),
        "report_valid_rate": mean(bool(metric["report_valid"]) for metric in metrics),
        "tool_selection_accuracy": mean(metric["tool_selection_accuracy"] for metric in metrics),
        "tool_success_rate": ratio(
            sum(metric["tool_successes"] for metric in metrics),
            sum(metric["tool_calls"] for metric in metrics),
        ),
        "evidence_grounding_rate": mean(
            metric["evidence_reference_precision"] for metric in metrics
        ),
        "numeric_evidence_grounding_rate": mean(
            metric["numeric_evidence_grounding"] for metric in metrics
        ),
        "duplicate_tool_call_rate": ratio(
            sum(metric["duplicate_tool_calls"] for metric in metrics),
            sum(metric["tool_calls"] for metric in metrics),
        ),
        "cache_hit_rate": ratio(
            sum(metric["cache_hits"] for metric in metrics),
            sum(metric["tool_calls"] for metric in metrics),
        ),
        "data_consistency_rate": (
            ratio(consistent_pairs, consistency_comparisons)
            if consistency_comparisons
            else None
        ),
        "data_consistency_comparisons": consistency_comparisons,
        "average_duration_seconds": mean(durations),
        "p50_duration_seconds": percentile(durations, 0.50),
        "p95_duration_seconds": percentile(durations, 0.95),
        "total_tokens": sum(tokens),
        "average_tokens": mean(tokens),
    }
