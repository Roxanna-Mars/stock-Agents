"""Normalize token-usage metadata from LangChain AI messages."""

from collections.abc import Sequence
from typing import Any


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def collect_token_usage(messages: Sequence[Any]) -> dict[str, int]:
    totals = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    for message in messages:
        usage = getattr(message, "usage_metadata", None) or {}
        if not usage:
            response_metadata = getattr(message, "response_metadata", None) or {}
            usage = response_metadata.get("token_usage", {})

        input_tokens = _as_int(
            usage.get("input_tokens", usage.get("prompt_tokens", 0))
        )
        output_tokens = _as_int(
            usage.get("output_tokens", usage.get("completion_tokens", 0))
        )
        total_tokens = _as_int(usage.get("total_tokens", 0))
        if total_tokens == 0:
            total_tokens = input_tokens + output_tokens

        totals["input_tokens"] += input_tokens
        totals["output_tokens"] += output_tokens
        totals["total_tokens"] += total_tokens

    return totals
