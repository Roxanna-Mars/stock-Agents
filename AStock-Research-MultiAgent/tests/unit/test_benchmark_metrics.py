from evaluation.failure_analysis import attribute_failures
from evaluation.metrics import aggregate_results, score_case


CASE = {
    "expected_agents": ["main", "summary_agent"],
    "expected_tool_groups": [["get_profit_data"], ["get_stock_basic_info"]],
    "forbidden_tools": ["crawl_news"],
    "required_terms": ["基本面", "风险"],
    "companies": ["贵州茅台"],
    "stock_codes": ["sh.600519"],
}


def test_case_metrics_cover_tools_grounding_and_tokens():
    artifacts = {
        "execution_info": {"success": True},
        "agents": {
            "main": {"status": "completed"},
            "summary_agent": {"status": "completed"},
        },
        "tool_calls": [
            {
                "tool_name": "get_profit_data",
                "output": "净利润 123.45",
                "success": True,
                "duplicate_call": False,
                "queue_wait_seconds": 1,
                "execution_time_seconds": 2,
            },
            {
                "tool_name": "get_stock_basic_info",
                "output": "代码 sh.600519",
                "success": True,
                "duplicate_call": False,
                "queue_wait_seconds": 0,
                "execution_time_seconds": 1,
            },
        ],
        "token_usage": {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120},
        "evidence_records": [
            {"evidence_id": "E-FUNDAMENTAL-1"},
        ],
        "report": "贵州茅台 sh.600519 基本面净利润为123.45 [E-FUNDAMENTAL-1]，风险可控。",
    }

    metrics = score_case(CASE, artifacts, 10, 0, None)

    assert metrics["task_success"] is True
    assert metrics["tool_selection_accuracy"] == 1.0
    assert metrics["numeric_evidence_grounding"] == 1.0
    assert metrics["evidence_reference_precision"] == 1.0
    assert metrics["token_usage"]["total_tokens"] == 120
    assert attribute_failures(metrics, None) == []


def test_failure_attribution_and_aggregation():
    artifacts = {
        "execution_info": {"success": False},
        "agents": {"main": {"status": "started"}},
        "tool_calls": [
            {
                "tool_name": "crawl_news",
                "output": "Error: network",
                "success": False,
                "duplicate_call": True,
            }
        ],
        "token_usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        "evidence_records": [],
        "report": "",
    }

    metrics = score_case(CASE, artifacts, 900, -1, "timeout after 900s")
    failures = attribute_failures(metrics, "timeout after 900s")
    summary = aggregate_results([{"metrics": metrics}])

    assert "workflow_timeout" in failures
    assert "agent_incomplete" in failures
    assert "tool_misselection" in failures
    assert "duplicate_tool_call" in failures
    assert summary["task_success_rate"] == 0
