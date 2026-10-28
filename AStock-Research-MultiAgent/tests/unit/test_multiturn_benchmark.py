from pathlib import Path

import pytest

from evaluation.multiturn_schema import load_multiturn_benchmark
from evaluation.run_multiturn_benchmark import run


def test_multiturn_benchmark_covers_required_categories():
    path = Path("evaluation/multiturn_benchmark.jsonl")
    cases = load_multiturn_benchmark(path)
    categories = {case.category for case in cases}

    assert len(cases) >= 12
    assert {"coreference", "comparison", "switch", "cancel", "clarification", "resume"} <= categories


@pytest.mark.asyncio
async def test_multiturn_benchmark_runner_produces_bounded_metrics():
    result = await run(Path("evaluation/multiturn_benchmark.jsonl"))

    assert result["metrics"]["turns"] >= 20
    for name in (
        "intent_accuracy",
        "intent_shift_macro_f1",
        "state_update_accuracy",
        "agent_routing_f1",
        "task_success_rate",
    ):
        assert 0.0 <= result["metrics"][name] <= 1.0
