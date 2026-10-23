from langchain_core.messages import AIMessage, ToolMessage

from src.utils.evidence import extract_evidence, evidence_reference_stats


def test_extract_evidence_links_tool_call_arguments_and_output():
    messages = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "get_profit_data",
                    "args": {"code": "sh.600519"},
                    "id": "call-1",
                    "type": "tool_call",
                }
            ],
        ),
        ToolMessage(
            content="net profit: 123.45",
            tool_call_id="call-1",
            name="get_profit_data",
        ),
    ]

    records = extract_evidence(messages, "fundamental_agent")

    assert records == [
        {
            "evidence_id": "E-FUNDAMENTAL-1",
            "agent_name": "fundamental_agent",
            "tool_name": "get_profit_data",
            "tool_call_id": "call-1",
            "arguments": {"code": "sh.600519"},
            "content": "net profit: 123.45",
            "content_truncated": False,
            "success": True,
            "error_type": None,
        }
    ]


def test_evidence_reference_stats_detect_invalid_ids_and_coverage():
    records = [
        {"evidence_id": "E-FUNDAMENTAL-1"},
        {"evidence_id": "E-VALUE-1"},
    ]
    stats = evidence_reference_stats(
        "Profit improved [E-FUNDAMENTAL-1], but [E-MADE-UP-9] is invalid.",
        records,
    )

    assert stats["evidence_references"] == 2
    assert stats["valid_evidence_references"] == 1
    assert stats["evidence_reference_precision"] == 0.5
    assert stats["evidence_reference_coverage"] == 0.5
