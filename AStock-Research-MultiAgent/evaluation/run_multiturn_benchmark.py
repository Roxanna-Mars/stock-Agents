"""Run the offline multi-turn benchmark without calling tools or a paid LLM."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from uuid import uuid4

from evaluation.multiturn_metrics import set_f1, summarize_turn_results
from evaluation.multiturn_schema import load_multiturn_benchmark
from src.dialogue.intent_service import ContextualIntentService
from src.dialogue.models import DialogueTaskState
from src.dialogue.state_reducer import apply_dialogue_turn
from src.planning.contextual_planner import plan_contextual_turn


async def run(path: Path) -> dict:
    service = ContextualIntentService(use_llm=False)
    rows = []
    for case in load_multiturn_benchmark(path):
        state = DialogueTaskState(session_id=f"benchmark-{uuid4()}")
        for expected in case.turns:
            turn = await service.parse(expected.query, state)
            state = apply_dialogue_turn(state, turn, query=expected.query)
            resolution = plan_contextual_turn(expected.query, turn, state)
            actual_tickers = [stock.code or stock.name or "" for stock in state.tickers]
            actual_dimensions = [item.value for item in state.analysis_dimensions]
            state_ok = (
                actual_tickers == expected.tickers
                and actual_dimensions == expected.dimensions
                and state.task_status == expected.task_status
            )
            routing_f1 = set_f1(expected.selected_agents, resolution.selected_agents)
            row = {
                "dialogue_id": case.dialogue_id,
                "category": case.category,
                "query": expected.query,
                "expected_change": expected.intent_change,
                "actual_change": turn.intent_change.value,
                "intent_ok": turn.utterance_intent.value == expected.intent,
                "state_ok": state_ok,
                "routing_f1": routing_f1,
                "execute_ok": resolution.should_execute == expected.should_execute,
            }
            row["turn_success"] = all(
                (
                    row["intent_ok"],
                    row["expected_change"] == row["actual_change"],
                    row["state_ok"],
                    row["routing_f1"] == 1.0,
                    row["execute_ok"],
                )
            )
            rows.append(row)
    return {"metrics": summarize_turn_results(rows), "turns": rows}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--benchmark",
        type=Path,
        default=Path("evaluation/multiturn_benchmark.jsonl"),
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = asyncio.run(run(args.benchmark))
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
