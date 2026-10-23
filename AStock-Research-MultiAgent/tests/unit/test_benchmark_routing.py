import json
from pathlib import Path

from src.planning.query_planner import plan_query


AGENT_LOG_NAMES = {
    "fundamental": "fundamental_agent",
    "technical": "technical_agent",
    "value": "value_agent",
    "news": "news_agent",
    "comparison": "comparison_agent",
}


def test_every_benchmark_case_routes_to_expected_research_agents():
    benchmark_path = Path(__file__).parents[2] / "evaluation" / "benchmark_v1.jsonl"
    cases = [
        json.loads(line)
        for line in benchmark_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    mismatches = []
    for case in cases:
        planned = [
            AGENT_LOG_NAMES[name]
            for name in plan_query(case["query"])["requested_agents"]
        ]
        expected = [
            name
            for name in case["expected_agents"]
            if name not in {"main", "summary_agent"}
        ]
        if planned != expected:
            mismatches.append((case["id"], planned, expected))

    assert mismatches == []
