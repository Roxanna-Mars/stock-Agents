"""Schema validation for versioned agent benchmark cases."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = {
    "id",
    "category",
    "query",
    "companies",
    "stock_codes",
    "expected_agents",
    "expected_tool_groups",
    "forbidden_tools",
    "required_terms",
    "support_level",
}
VALID_SUPPORT_LEVELS = {"supported", "target"}


def validate_case(case: dict[str, Any], source: str = "case") -> None:
    missing = REQUIRED_FIELDS - case.keys()
    if missing:
        raise ValueError(f"{source} missing fields: {sorted(missing)}")
    if not isinstance(case["id"], str) or not case["id"].strip():
        raise ValueError(f"{source} id must be a non-empty string")
    if not isinstance(case["query"], str) or not case["query"].strip():
        raise ValueError(f"{source} query must be a non-empty string")
    for field in (
        "companies",
        "stock_codes",
        "expected_agents",
        "expected_tool_groups",
        "forbidden_tools",
        "required_terms",
    ):
        if not isinstance(case[field], list):
            raise ValueError(f"{source} {field} must be a list")
    if not all(isinstance(group, list) and group for group in case["expected_tool_groups"]):
        raise ValueError(f"{source} expected_tool_groups must contain non-empty lists")
    if case["support_level"] not in VALID_SUPPORT_LEVELS:
        raise ValueError(
            f"{source} support_level must be one of {sorted(VALID_SUPPORT_LEVELS)}"
        )


def load_benchmark(path: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    ids: set[str] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        case = json.loads(line)
        validate_case(case, f"{path}:{line_number}")
        if case["id"] in ids:
            raise ValueError(f"{path}:{line_number} duplicate id: {case['id']}")
        ids.add(case["id"])
        cases.append(case)
    if not cases:
        raise ValueError(f"{path} contains no benchmark cases")
    return cases
