"""Run controlled architecture ablations over the same benchmark cases."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path

from evaluation.benchmark_schema import load_benchmark
from evaluation.comparison import compare_payloads, render_comparison_markdown
from evaluation.failure_analysis import summarize_failures
from evaluation.metrics import aggregate_results
from evaluation.run_benchmark import DEFAULT_BENCHMARK, RESULTS_DIR, run_case


ARCHITECTURES = ("single_agent", "fixed_workflow", "react_multi_agent")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run architecture ablation experiments")
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--category", action="append", default=[])
    parser.add_argument("--architecture", action="append", choices=ARCHITECTURES, default=[])
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def select_cases(cases: list[dict], args: argparse.Namespace) -> list[dict]:
    if args.case_id:
        wanted = set(args.case_id)
        known = {case["id"] for case in cases}
        unknown = wanted - known
        if unknown:
            raise ValueError(f"unknown case ids: {sorted(unknown)}")
        cases = [case for case in cases if case["id"] in wanted]
    if args.category:
        wanted_categories = set(args.category)
        cases = [case for case in cases if case["category"] in wanted_categories]
    return cases


def main() -> int:
    args = parse_args()
    cases = select_cases(load_benchmark(args.benchmark), args)
    architectures = args.architecture or list(ARCHITECTURES)
    if args.repeats < 1:
        raise ValueError("--repeats must be at least 1")
    if not cases:
        raise ValueError("no benchmark cases selected")
    planned_runs = len(cases) * len(architectures) * args.repeats
    print(
        json.dumps(
            {
                "cases": len(cases),
                "architectures": architectures,
                "repeats": args.repeats,
                "planned_runs": planned_runs,
            },
            ensure_ascii=False,
        )
    )
    if args.dry_run:
        print("Ablation plan validated; no model or data API was called.")
        return 0
    if not args.case_id and not args.category and not args.all:
        print("Refusing to run the full paid ablation without --all.")
        return 2
    if os.getenv("RUN_LIVE_LLM") != "1":
        print("Refusing paid ablation. Set RUN_LIVE_LLM=1 explicitly to continue.")
        return 2

    output_dir = args.output_dir or (
        RESULTS_DIR / f"ablation_{datetime.now():%Y%m%d_%H%M%S}"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    payloads = {}
    for architecture in architectures:
        results = []
        for case in cases:
            for repeat in range(1, args.repeats + 1):
                print(f"[{architecture}] [{case['id']} {repeat}/{args.repeats}]")
                results.append(run_case(case, repeat, args.timeout, architecture))
        payload = {
            "benchmark": args.benchmark.name,
            "generated_at": datetime.now().isoformat(),
            "model": os.getenv("OPENAI_COMPATIBLE_MODEL", "Not Set"),
            "base_url": os.getenv("OPENAI_COMPATIBLE_BASE_URL", "Not Set"),
            "architecture": architecture,
            "summary": aggregate_results(results),
            "failure_summary": summarize_failures(results),
            "results": results,
        }
        payloads[architecture] = payload
        (output_dir / f"{architecture}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    comparisons = {}
    candidate = payloads.get("react_multi_agent")
    if candidate:
        for baseline_name in ("single_agent", "fixed_workflow"):
            if baseline_name not in payloads:
                continue
            comparison = compare_payloads(payloads[baseline_name], candidate)
            comparisons[f"{baseline_name}_vs_react_multi_agent"] = comparison
            (output_dir / f"{baseline_name}_vs_react_multi_agent.md").write_text(
                render_comparison_markdown(comparison),
                encoding="utf-8",
            )
        available_baselines = [
            name
            for name in ("single_agent", "fixed_workflow")
            if name in payloads
        ]
        if available_baselines:
            best_baseline_name = max(
                available_baselines,
                key=lambda name: payloads[name]["summary"].get(
                    "task_success_rate", 0
                ),
            )
            best_comparison = compare_payloads(
                payloads[best_baseline_name],
                candidate,
            )
            best_comparison["selection_rule"] = (
                "highest task_success_rate among available baselines"
            )
            comparisons["best_baseline_vs_react_multi_agent"] = best_comparison
            (output_dir / "best_baseline_vs_react_multi_agent.md").write_text(
                render_comparison_markdown(best_comparison),
                encoding="utf-8",
            )
    (output_dir / "comparisons.json").write_text(
        json.dumps(comparisons, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Ablation results: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
