"""Schema for dialogue-level intent and routing benchmarks."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class ExpectedTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str
    intent: str
    intent_change: str
    tickers: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    selected_agents: list[str] = Field(default_factory=list)
    should_execute: bool = True
    task_status: str = "active"


class DialogueBenchmarkCase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dialogue_id: str
    category: str
    turns: list[ExpectedTurn]


def load_multiturn_benchmark(path: str | Path) -> list[DialogueBenchmarkCase]:
    cases: list[DialogueBenchmarkCase] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                cases.append(DialogueBenchmarkCase.model_validate_json(line))
            except Exception as error:
                raise ValueError(f"invalid benchmark line {line_number}: {error}") from error
    return cases
