"""Deterministic metrics for context-aware dialogue evaluation."""

from __future__ import annotations

from collections import Counter
from typing import Any


def classification_macro_f1(expected: list[str], actual: list[str]) -> float:
    labels = sorted(set(expected) | set(actual))
    if not labels:
        return 1.0
    scores: list[float] = []
    for label in labels:
        tp = sum(e == label and a == label for e, a in zip(expected, actual))
        fp = sum(e != label and a == label for e, a in zip(expected, actual))
        fn = sum(e == label and a != label for e, a in zip(expected, actual))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        scores.append(
            2 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )
    return sum(scores) / len(scores)


def set_f1(expected: list[str], actual: list[str]) -> float:
    expected_set, actual_set = set(expected), set(actual)
    if not expected_set and not actual_set:
        return 1.0
    overlap = len(expected_set & actual_set)
    precision = overlap / len(actual_set) if actual_set else 0.0
    recall = overlap / len(expected_set) if expected_set else 0.0
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def summarize_turn_results(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    if not total:
        return {"turns": 0}
    expected_changes = [row["expected_change"] for row in rows]
    actual_changes = [row["actual_change"] for row in rows]
    return {
        "turns": total,
        "intent_accuracy": sum(row["intent_ok"] for row in rows) / total,
        "intent_shift_macro_f1": classification_macro_f1(
            expected_changes, actual_changes
        ),
        "state_update_accuracy": sum(row["state_ok"] for row in rows) / total,
        "agent_routing_f1": sum(row["routing_f1"] for row in rows) / total,
        "task_success_rate": sum(row["turn_success"] for row in rows) / total,
        "failures_by_category": dict(
            Counter(row["category"] for row in rows if not row["turn_success"])
        ),
    }
