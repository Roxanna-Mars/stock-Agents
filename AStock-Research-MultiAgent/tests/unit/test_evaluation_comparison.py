from evaluation.comparison import compare_payloads, render_comparison_markdown
from evaluation.metrics import aggregate_results


def _result(output_hash: str):
    return {
        "metrics": {
            "task_success": True,
            "workflow_success": True,
            "report_valid": True,
            "tool_selection_accuracy": 1.0,
            "tool_successes": 1,
            "tool_calls": 1,
            "numeric_evidence_grounding": 1.0,
            "evidence_reference_precision": 1.0,
            "duplicate_tool_calls": 0,
            "cache_hits": 0,
            "duration_seconds": 10.0,
            "token_usage": {"total_tokens": 100},
            "tool_output_signatures": [
                {"fingerprint": "same-input", "output_hash": output_hash}
            ],
        }
    }


def test_consistency_metric_compares_repeated_tool_outputs():
    consistent = aggregate_results([_result("hash-a"), _result("hash-a")])
    inconsistent = aggregate_results([_result("hash-a"), _result("hash-b")])

    assert consistent["data_consistency_rate"] == 1.0
    assert consistent["data_consistency_comparisons"] == 1
    assert inconsistent["data_consistency_rate"] == 0.0


def test_result_comparison_calculates_resume_ready_deltas():
    baseline = {
        "architecture": "fixed_workflow",
        "summary": {
            "task_success_rate": 0.6,
            "average_duration_seconds": 100,
            "p50_duration_seconds": 90,
            "p95_duration_seconds": 150,
            "average_tokens": 1000,
        },
        "failure_summary": {"tool_omission": 4},
    }
    candidate = {
        "architecture": "react_multi_agent",
        "summary": {
            "task_success_rate": 0.8,
            "average_duration_seconds": 75,
            "p50_duration_seconds": 70,
            "p95_duration_seconds": 100,
            "average_tokens": 900,
        },
        "failure_summary": {"tool_omission": 1},
    }

    comparison = compare_payloads(baseline, candidate)

    assert comparison["percentage_point_deltas"]["task_success_rate"] == 20.0
    assert comparison["relative_changes_percent"]["average_duration_seconds"] == -25.0
    assert comparison["relative_changes_percent"]["average_tokens"] == -10.0
    assert comparison["failure_count_deltas"]["tool_omission"] == -3
    assert "fixed_workflow" in render_comparison_markdown(comparison)
