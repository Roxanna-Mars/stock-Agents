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

from evaluation.benchmark_schema import load_benchmark
from evaluation.failure_analysis import attribute_failures, summarize_failures
from evaluation.metrics import aggregate_results, score_case
from evaluation.trace_reader import read_execution_artifacts


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOGS_DIR = PROJECT_ROOT / "logs"
DEFAULT_BENCHMARK = Path(__file__).with_name("benchmark_v1.jsonl")
RESULTS_DIR = Path(__file__).with_name("results")


def execution_dirs() -> set[Path]:
    if not LOGS_DIR.exists():
        return set()
    return {path.resolve() for path in LOGS_DIR.iterdir() if path.is_dir()}


def select_cases(cases: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    selected = cases
    if args.case_id:
        wanted = set(args.case_id)
        known = {case["id"] for case in cases}
        unknown = wanted - known
        if unknown:
            raise ValueError(f"unknown case ids: {sorted(unknown)}")
        selected = [case for case in selected if case["id"] in wanted]
    if args.category:
        wanted_categories = set(args.category)
        selected = [case for case in selected if case["category"] in wanted_categories]
    return selected


def run_case(
    case: dict[str, Any],
    repeat: int,
    timeout: int,
    architecture: str = "react_multi_agent",
) -> dict[str, Any]:
    before = execution_dirs()
    env = os.environ.copy()
    env.update({"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"})
    started = time.monotonic()
    return_code = None
    stdout = ""
    stderr = ""
    process_error = None
    try:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.main",
                "--command",
                case["query"],
                "--architecture",
                architecture,
            ],
            cwd=PROJECT_ROOT,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        return_code = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as exc:
        return_code = -1
        process_error = f"timeout after {timeout}s"
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""

    duration = time.monotonic() - started
    created = execution_dirs() - before
    execution_dir = max(created, key=lambda path: path.stat().st_mtime) if created else None
    artifacts = read_execution_artifacts(execution_dir)
    metrics = score_case(
        case,
        artifacts,
        duration,
        return_code,
        process_error,
        architecture=architecture,
    )
    failures = attribute_failures(metrics, process_error)
    return {
        "case_id": case["id"],
        "category": case["category"],
        "support_level": case["support_level"],
        "architecture": architecture,
        "repeat": repeat,
        "query": case["query"],
        "return_code": return_code,
        "process_error": process_error,
        "execution_dir": str(execution_dir) if execution_dir else None,
        "metrics": metrics,
        "failure_modes": failures,
        "stdout_tail": stdout[-2000:],
        "stderr_tail": stderr[-2000:],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the versioned financial-agent benchmark")
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--category", action="append", default=[])
    parser.add_argument("--all", action="store_true", help="explicitly run every selected case")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--architecture",
        choices=("single_agent", "fixed_workflow", "react_multi_agent"),
        default="react_multi_agent",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cases = select_cases(load_benchmark(args.benchmark), args)
    if args.repeats < 1:
        raise ValueError("--repeats must be at least 1")
    if not cases:
        raise ValueError("no benchmark cases selected")

    categories: dict[str, int] = {}
    for case in cases:
        categories[case["category"]] = categories.get(case["category"], 0) + 1
    print(json.dumps({"cases": len(cases), "categories": categories}, ensure_ascii=False))
    if args.dry_run:
        print("Benchmark schema validation passed; no model or data API was called.")
        return 0

    if not args.case_id and not args.category and not args.all:
        print(
            "Refusing to run all paid cases implicitly. Select --case-id/--category or pass --all.",
            file=sys.stderr,
        )
        return 2

    if os.getenv("RUN_LIVE_LLM") != "1":
        print(
            "Refusing paid benchmark. Set RUN_LIVE_LLM=1 explicitly to continue.",
            file=sys.stderr,
        )
        return 2

    results = []
    for case in cases:
        for repeat in range(1, args.repeats + 1):
            print(f"[{case['id']} {repeat}/{args.repeats}] {case['query']}")
            result = run_case(case, repeat, args.timeout, args.architecture)
            results.append(result)
            status = "PASS" if result["metrics"]["task_success"] else "FAIL"
            print(f"  {status} {result['metrics']['duration_seconds']:.1f}s {result['failure_modes']}")

    payload = {
        "benchmark": args.benchmark.name,
        "generated_at": datetime.now().isoformat(),
        "model": os.getenv("OPENAI_COMPATIBLE_MODEL", "Not Set"),
        "base_url": os.getenv("OPENAI_COMPATIBLE_BASE_URL", "Not Set"),
        "architecture": args.architecture,
        "summary": aggregate_results(results),
        "failure_summary": summarize_failures(results),
        "results": results,
    }
    output = args.output
    if output is None:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        output = RESULTS_DIR / f"benchmark_{datetime.now():%Y%m%d_%H%M%S}.json"
    elif not output.is_absolute():
        output = PROJECT_ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    print(f"Results: {output}")
    return 0 if all(result["metrics"]["task_success"] for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
