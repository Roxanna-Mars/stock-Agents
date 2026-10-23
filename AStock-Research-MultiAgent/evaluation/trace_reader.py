"""Read execution artifacts without coupling metrics to logger internals."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return records
    for line in lines:
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def read_execution_artifacts(execution_dir: Path | None) -> dict[str, Any]:
    if execution_dir is None:
        return {
            "execution_info": {},
            "agents": {},
            "tool_calls": [],
            "evidence_records": [],
            "token_usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            "report": "",
        }

    agents = {}
    for path in (execution_dir / "agents").glob("*_execution.json"):
        data = read_json(path)
        agents[data.get("agent_name", path.stem.removesuffix("_execution"))] = data

    tool_calls = []
    for path in (execution_dir / "tools").glob("*.jsonl"):
        tool_calls.extend(read_jsonl(path))

    token_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    for path in (execution_dir / "llm_interactions").glob("*.json"):
        interaction = read_json(path)
        usage = interaction.get("performance", {}).get("token_usage") or {}
        for key in token_usage:
            token_usage[key] += int(usage.get(key, 0) or 0)

    report_path = execution_dir / "reports" / "final_report.md"
    report = (
        report_path.read_text(encoding="utf-8", errors="replace")
        if report_path.exists()
        else ""
    )
    return {
        "execution_info": read_json(execution_dir / "execution_info.json"),
        "agents": agents,
        "tool_calls": tool_calls,
        "evidence_records": read_jsonl(execution_dir / "evidence" / "evidence.jsonl"),
        "token_usage": token_usage,
        "report": report,
    }
