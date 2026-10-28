"""Build compact, traceable evidence records from ReAct message histories."""

from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage

from src.domain.models import EvidenceRecord
from src.utils.tool_result_utils import classify_tool_error


EVIDENCE_REFERENCE = re.compile(r"\[(E-[A-Z0-9_-]+)\]")
PROVENANCE_REFERENCE = re.compile(r"\[((?:E|D|C|CL|R)-[A-Z0-9_-]+)\]")


def extract_evidence(
    messages: list[Any],
    agent_name: str,
    max_output_chars: int = 4000,
) -> list[dict[str, Any]]:
    """Return the legacy dictionary format consumed by the current workflow."""
    return [
        record.to_legacy_dict()
        for record in extract_evidence_records(messages, agent_name, max_output_chars)
    ]


def extract_evidence_records(
    messages: list[Any],
    agent_name: str,
    max_output_chars: int = 4000,
) -> list[EvidenceRecord]:
    """Build typed, hash-addressed evidence records from tool messages."""
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
    evidence: list[EvidenceRecord] = []
    for index, message in enumerate(
        (item for item in messages if isinstance(item, ToolMessage)),
        1,
    ):
        call_id = str(getattr(message, "tool_call_id", ""))
        call = calls.get(call_id, {})
        content = str(message.content)
        error_type = classify_tool_error(content)
        evidence.append(
            EvidenceRecord.create(
                evidence_id=f"E-{prefix}-{index}",
                agent_name=agent_name,
                tool_name=getattr(message, "name", None) or call.get("tool_name"),
                tool_call_id=call_id,
                arguments=call.get("arguments", {}),
                content=content,
                stored_content=content[:max_output_chars],
                success=error_type is None,
                error_type=error_type,
            )
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


def provenance_reference_stats(
    report: str,
    valid_record_ids: set[str],
) -> dict[str, int | float]:
    """Measure report references across evidence, data, calculation and claims."""
    references = PROVENANCE_REFERENCE.findall(report)
    valid_references = [item for item in references if item in valid_record_ids]
    return {
        "provenance_references": len(references),
        "valid_provenance_references": len(valid_references),
        "provenance_reference_precision": (
            len(valid_references) / len(references) if references else 0.0
        ),
        "provenance_reference_coverage": (
            len(set(valid_references)) / len(valid_record_ids)
            if valid_record_ids
            else 0.0
        ),
    }
