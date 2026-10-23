"""Helpers for deciding whether an agent obtained usable tool data."""

from collections.abc import Iterable, Sequence
from typing import Any

from langchain_core.messages import ToolMessage


TOOL_ERROR_MARKERS = (
    "error:",
    "用户未登录",
    "10001001",
    "网络接收错误",
    "could not connect",
    "分析生成失败",
)


def classify_tool_error(content: Any, exception: BaseException | None = None) -> str | None:
    """Return a stable error category for evaluation while preserving raw output."""
    if exception is not None:
        name = type(exception).__name__.casefold()
        message = str(exception).casefold()
        if "timeout" in name or "timeout" in message:
            return "timeout"
        if "validation" in name or "argument" in message or "parameter" in message:
            return "invalid_parameters"
        return "exception"

    text = str(content).casefold()
    if "10001001" in text or "用户未登录" in text:
        return "authentication_state"
    if "网络接收错误" in text or "could not connect" in text:
        return "network"
    if "参数" in text and ("错误" in text or "无效" in text):
        return "invalid_parameters"
    if any(marker.casefold() in text for marker in TOOL_ERROR_MARKERS):
        return "tool_error"
    return None


def inspect_tool_results(
    messages: Sequence[Any],
    ignored_tools: Iterable[str] = (),
) -> dict[str, int]:
    """Count usable and failed tool results, excluding non-data helper tools."""
    ignored_tool_names = set(ignored_tools)
    relevant_messages = [
        message
        for message in messages
        if isinstance(message, ToolMessage)
        and getattr(message, "name", None) not in ignored_tool_names
    ]

    failed_count = 0
    for message in relevant_messages:
        content = str(message.content).casefold()
        status = str(getattr(message, "status", "")).casefold()
        if status == "error" or any(
            marker.casefold() in content for marker in TOOL_ERROR_MARKERS
        ):
            failed_count += 1

    total_count = len(relevant_messages)
    return {
        "total": total_count,
        "failed": failed_count,
        "succeeded": total_count - failed_count,
    }
