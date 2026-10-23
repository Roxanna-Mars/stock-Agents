from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOGS_DIR = PROJECT_ROOT / "logs"
DEFAULT_CASES = Path(__file__).with_name("cases.jsonl")
RESULTS_DIR = Path(__file__).with_name("results")
EXPECTED_AGENTS = {
    "fundamental_agent",
    "main",
    "news_agent",
    "summary_agent",
    "technical_agent",
    "value_agent",
}
REQUIRED_SECTIONS = (
    "基本面分析",
    "技术分析",
    "估值分析",
    "新闻分析",
    "风险因素",
    "投资建议",
)


def load_cases(path: Path) -> list[dict[str, Any]]:
    cases = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        case = json.loads(line)
        missing = {"id", "query", "company", "stock_code"} - case.keys()
        if missing:
            raise ValueError(f"{path}:{line_number} missing fields: {sorted(missing)}")
        cases.append(case)
    return cases


def execution_dirs() -> set[Path]:
    if not LOGS_DIR.exists():
        return set()
    return {path.resolve() for path in LOGS_DIR.iterdir() if path.is_dir()}


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def inspect_execution(
    case: dict[str, Any],
    repeat: int,
    completed: subprocess.CompletedProcess[str] | None,
    execution_dir: Path | None,
    duration: float,
    process_error: str | None,
) -> dict[str, Any]:
    info = read_json(execution_dir / "execution_info.json") if execution_dir else {}
    report_path = execution_dir / "reports" / "final_report.md" if execution_dir else None
    report = ""
    if report_path and report_path.exists():
        report = report_path.read_text(encoding="utf-8", errors="replace")

    agent_statuses: dict[str, str] = {}
    agent_errors: dict[str, str] = {}
    tool_results = {"total": 0, "succeeded": 0, "failed": 0}
    agents_dir = execution_dir / "agents" if execution_dir else None
    if agents_dir and agents_dir.exists():
        for path in agents_dir.glob("*_execution.json"):
            agent = read_json(path)
            name = agent.get("agent_name", path.stem.removesuffix("_execution"))
            agent_statuses[name] = agent.get("status", "unknown")
            if agent.get("error"):
                agent_errors[name] = str(agent["error"])
            stats = agent.get("output_data", {}).get("tool_results", {})
            for key in tool_results:
                tool_results[key] += int(stats.get(key, 0) or 0)

    missing_sections = [section for section in REQUIRED_SECTIONS if section not in report]
    missing_identifiers = [
        value for value in (case["company"], case["stock_code"]) if value not in report
    ]
    all_agents_completed = (
        set(agent_statuses) == EXPECTED_AGENTS
        and all(status == "completed" for status in agent_statuses.values())
    )
    return_code = completed.returncode if completed else None
    workflow_success = bool(info.get("success"))
    valid_report = (
        len(report) >= 3000
        and not missing_sections
        and not missing_identifiers
        and report.count("分析基准时间") == 1
    )
    passed = (
        return_code == 0
        and workflow_success
        and valid_report
        and all_agents_completed
        and process_error is None
    )

    return {
        "case_id": case["id"],
        "query": case["query"],
        "repeat": repeat,
        "return_code": return_code,
        "duration_seconds": round(duration, 3),
        "execution_dir": str(execution_dir) if execution_dir else None,
        "workflow_success": workflow_success,
        "report_exists": bool(report),
        "report_length": len(report),
        "missing_sections": missing_sections,
        "missing_identifiers": missing_identifiers,
        "baseline_time_count": report.count("分析基准时间"),
        "agent_statuses": agent_statuses,
        "agent_errors": agent_errors,
        "tool_results": tool_results,
        "valid_report": valid_report,
        "process_error": process_error,
        "stdout_tail": completed.stdout[-2000:] if completed else "",
        "stderr_tail": completed.stderr[-2000:] if completed else "",
        "passed": passed,
    }


def run_case(case: dict[str, Any], repeat: int, timeout: int) -> dict[str, Any]:
    before = execution_dirs()
    env = os.environ.copy()
    env.update({"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"})
    started = time.monotonic()
    completed = None
    process_error = None
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "src.main", "--command", case["query"]],
            cwd=PROJECT_ROOT,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        process_error = f"timeout after {timeout}s"
        completed = subprocess.CompletedProcess(
            exc.cmd,
            returncode=-1,
            stdout=(exc.stdout or "") if isinstance(exc.stdout, str) else "",
            stderr=(exc.stderr or "") if isinstance(exc.stderr, str) else "",
        )
    duration = time.monotonic() - started

    created = execution_dirs() - before
    execution_dir = max(created, key=lambda path: path.stat().st_mtime) if created else None
    return inspect_execution(
        case, repeat, completed, execution_dir, duration, process_error
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run paid end-to-end agent evaluations")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if os.getenv("RUN_LIVE_LLM") != "1":
        print(
            "Refusing to call the paid API. Set RUN_LIVE_LLM=1 explicitly to continue.",
            file=sys.stderr,
        )
        return 2
    if args.repeats < 1:
        raise ValueError("--repeats must be at least 1")

    cases = load_cases(args.cases)
    if args.case_id:
        selected = set(args.case_id)
        cases = [case for case in cases if case["id"] in selected]
        unknown = selected - {case["id"] for case in cases}
        if unknown:
            raise ValueError(f"unknown case ids: {sorted(unknown)}")

    results = []
    for case in cases:
        for repeat in range(1, args.repeats + 1):
            print(f"[{case['id']} {repeat}/{args.repeats}] running: {case['query']}")
            result = run_case(case, repeat, args.timeout)
            results.append(result)
            print(
                f"  {'PASS' if result['passed'] else 'FAIL'} "
                f"({result['duration_seconds']:.1f}s)"
            )

    output = args.output
    if output is None:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = RESULTS_DIR / f"evaluation_{timestamp}.json"
    elif not output.is_absolute():
        output = PROJECT_ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "generated_at": datetime.now().isoformat(),
        "model": os.getenv("OPENAI_COMPATIBLE_MODEL", "Not Set"),
        "base_url": os.getenv("OPENAI_COMPATIBLE_BASE_URL", "Not Set"),
        "results": results,
    }
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Results: {output}")
    return 0 if all(result["passed"] for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
