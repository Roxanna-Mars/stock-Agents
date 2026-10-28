import json
from pathlib import Path

from src.planning.direct_tool_planner import DirectToolPlanner


def test_direct_tool_benchmark_has_no_routing_regressions():
    benchmark_path = (
        Path(__file__).resolve().parents[2]
        / "evaluation"
        / "direct_tool_benchmark.jsonl"
    )
    cases = [
        json.loads(line)
        for line in benchmark_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    planner = DirectToolPlanner()

    assert len(cases) >= 20
    for case in cases:
        plan = planner.plan(case["query"])
        assert (plan is not None) is case["eligible"], case["id"]
        if plan is not None:
            assert plan.tool_name == case["expected_tool"], case["id"]
