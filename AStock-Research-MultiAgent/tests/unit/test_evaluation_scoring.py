from evaluation.score_results import percentile, summarize_results


def test_percentile_interpolates_values():
    assert percentile([10, 20, 30], 0.50) == 20
    assert percentile([10, 20], 0.95) == 19.5


def test_summary_calculates_core_rates_and_thresholds():
    payload = {
        "results": [
            {
                "passed": True,
                "workflow_success": True,
                "valid_report": True,
                "duration_seconds": 100,
                "agent_statuses": {"main": "completed", "summary_agent": "completed"},
                "agent_errors": {},
                "tool_results": {"total": 10, "succeeded": 9, "failed": 1},
                "stderr_tail": "",
            }
        ]
    }

    summary = summarize_results(payload)

    assert summary["overall_pass_rate"] == 1.0
    assert summary["agent_success_rate"] == 1.0
    assert summary["tool_success_rate"] == 0.9
    assert summary["passed_thresholds"] is True
