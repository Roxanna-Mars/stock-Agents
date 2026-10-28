from langchain_core.messages import AIMessage, ToolMessage

from src.domain.models import stable_content_hash
from src.utils.evidence import (
    evidence_reference_stats,
    extract_evidence,
    extract_evidence_records,
    provenance_reference_stats,
)


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


def test_typed_evidence_preserves_hash_of_full_untruncated_output():
    messages = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "get_stock_data",
                    "args": {"code": "sh.600519"},
                    "id": "call-1",
                    "type": "tool_call",
                }
            ],
        ),
        ToolMessage(
            content="1234567890",
            tool_call_id="call-1",
            name="get_stock_data",
        ),
    ]

    records = extract_evidence_records(messages, "technical_agent", max_output_chars=5)

    assert records[0].content == "12345"
    assert records[0].content_truncated is True
    assert records[0].content_hash == stable_content_hash("1234567890")


def test_provenance_reference_stats_supports_all_artifact_prefixes():
    stats = provenance_reference_stats(
        "Price [D-PRICE-1], value [C-DCF-1], claim [CL-1], bad [E-FAKE-1].",
        {"D-PRICE-1", "C-DCF-1", "CL-1"},
    )

    assert stats["provenance_references"] == 4
    assert stats["valid_provenance_references"] == 3
    assert stats["provenance_reference_precision"] == 0.75
    assert stats["provenance_reference_coverage"] == 1.0
