"""Build compact, traceable evidence records from ReAct message histories."""

from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage

from src.utils.tool_result_utils import classify_tool_error


EVIDENCE_REFERENCE = re.compile(r"\[(E-[A-Z0-9_-]+)\]")


def extract_evidence(
    messages: list[Any],
    agent_name: str,
    max_output_chars: int = 4000,
) -> list[dict[str, Any]]:
    calls: dict[str, dict[str, Any]] = {}
    for message in messages:
        if not isinstance(message, AIMessage):
            continue
        for call in getattr(message, "tool_calls", None) or []:
            call_id = str(call.get("id", ""))
            calls[call_id] = {
                "tool_name": call.get("name"),
                "arguments": call.get("args") or {},
            }

    prefix = agent_name.removesuffix("_agent").replace("_", "-").upper()
    evidence = []
    for index, message in enumerate(
        (item for item in messages if isinstance(item, ToolMessage)),
        1,
    ):
        call_id = str(getattr(message, "tool_call_id", ""))
        call = calls.get(call_id, {})
        content = str(message.content)
        error_type = classify_tool_error(content)
        evidence.append(
            {
                "evidence_id": f"E-{prefix}-{index}",
                "agent_name": agent_name,
                "tool_name": getattr(message, "name", None) or call.get("tool_name"),
                "tool_call_id": call_id,
                "arguments": call.get("arguments", {}),
                "content": content[:max_output_chars],
                "content_truncated": len(content) > max_output_chars,
                "success": error_type is None,
                "error_type": error_type,
            }
        )
    return evidence


def format_evidence_for_prompt(records: list[dict[str, Any]]) -> str:
    if not records:
        return "No traceable tool evidence was recorded."
    blocks = []
    for record in records:
        blocks.append(
            "\n".join(
                (
                    f"[{record['evidence_id']}]",
                    f"agent={record.get('agent_name')}",
                    f"tool={record.get('tool_name')}",
                    f"arguments={record.get('arguments')}",
                    f"success={record.get('success')}",
                    f"result={record.get('content', '')}",
                )
            )
        )
    return "\n\n".join(blocks)


def evidence_reference_stats(report: str, records: list[dict[str, Any]]) -> dict[str, int | float]:
    references = EVIDENCE_REFERENCE.findall(report)
    valid_ids = {record["evidence_id"] for record in records}
    valid_references = [reference for reference in references if reference in valid_ids]
    return {
        "evidence_records": len(records),
        "evidence_references": len(references),
        "valid_evidence_references": len(valid_references),
        "evidence_reference_precision": (
            len(valid_references) / len(references) if references else 0.0
        ),
        "evidence_reference_coverage": (
            len(set(valid_references)) / len(valid_ids) if valid_ids else 0.0
        ),
    }
