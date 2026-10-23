from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


RESULTS_DIR = Path(__file__).with_name("results")


def ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


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


def summarize_results(payload: dict[str, Any]) -> dict[str, Any]:
    results = payload.get("results", [])
    total = len(results)
    passed = sum(bool(result.get("passed")) for result in results)
    workflows = sum(bool(result.get("workflow_success")) for result in results)
    reports = sum(bool(result.get("valid_report")) for result in results)
    durations = [float(result.get("duration_seconds", 0)) for result in results]

    statuses = [
        status
        for result in results
        for status in result.get("agent_statuses", {}).values()
    ]
    tool_total = sum(result.get("tool_results", {}).get("total", 0) for result in results)
    tool_succeeded = sum(
        result.get("tool_results", {}).get("succeeded", 0) for result in results
    )
    error_parts = []
    for result in results:
        error_parts.append(str(result.get("process_error") or ""))
        error_parts.extend(
            str(error) for error in result.get("agent_errors", {}).values()
        )
        error_parts.append(str(result.get("stderr_tail") or ""))
    error_text = "\n".join(error_parts)

    summary = {
        "total_runs": total,
        "passed_runs": passed,
        "overall_pass_rate": ratio(passed, total),
        "workflow_success_rate": ratio(workflows, total),
        "valid_report_rate": ratio(reports, total),
        "agent_success_rate": ratio(statuses.count("completed"), len(statuses)),
        "tool_success_rate": ratio(tool_succeeded, tool_total),
        "average_duration_seconds": sum(durations) / len(durations) if durations else 0.0,
        "p50_duration_seconds": percentile(durations, 0.50),
        "p95_duration_seconds": percentile(durations, 0.95),
        "recursion_errors": error_text.lower().count("recursion"),
        "baostock_login_errors": error_text.count("10001001"),
    }
    summary["thresholds_met"] = {
        "overall_pass_rate_gte_95pct": summary["overall_pass_rate"] >= 0.95,
        "workflow_success_rate_gte_95pct": summary["workflow_success_rate"] >= 0.95,
        "valid_report_rate_eq_100pct": summary["valid_report_rate"] == 1.0,
        "tool_success_rate_gte_90pct": summary["tool_success_rate"] >= 0.90,
        "no_recursion_errors": summary["recursion_errors"] == 0,
        "no_baostock_login_errors": summary["baostock_login_errors"] == 0,
    }
    summary["passed_thresholds"] = all(summary["thresholds_met"].values())
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score an agent evaluation result")
    parser.add_argument("result", nargs="?", type=Path)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args()


def latest_result() -> Path:
    candidates = list(RESULTS_DIR.glob("evaluation_*.json"))
    if not candidates:
        raise FileNotFoundError("no evaluation results found")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def main() -> int:
    args = parse_args()
    result_path = args.result or latest_result()
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    summary = summarize_results(payload)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.strict and not summary["passed_thresholds"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
