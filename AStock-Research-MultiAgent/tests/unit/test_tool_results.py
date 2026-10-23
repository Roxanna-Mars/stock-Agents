from langchain_core.messages import ToolMessage

from src.utils.tool_result_utils import classify_tool_error, inspect_tool_results


def tool_message(content: str, call_id: str, name: str) -> ToolMessage:
    return ToolMessage(content=content, tool_call_id=call_id, name=name)


def test_baostock_login_error_is_failed():
    messages = [
        tool_message(
            "Error: 用户未登录 (10001001)",
            "1",
            "get_profit_data",
        ),
        tool_message(
            "| code | roe |\n| sh.600519 | 30 |",
            "2",
            "get_growth_data",
        ),
    ]

    assert inspect_tool_results(messages) == {
        "total": 2,
        "failed": 1,
        "succeeded": 1,
    }


def test_timeframe_helper_can_be_ignored():
    messages = [
        tool_message(
            "2026年08月-09月",
            "1",
            "get_market_analysis_timeframe",
        ),
        tool_message(
            "Error: 用户未登录 (10001001)",
            "2",
            "get_profit_data",
        ),
    ]

    assert inspect_tool_results(
        messages,
        ignored_tools={"get_market_analysis_timeframe"},
    ) == {
        "total": 1,
        "failed": 1,
        "succeeded": 0,
    }


def test_tool_error_classification_is_stable():
    assert classify_tool_error("10001001 用户未登录") == "authentication_state"
    assert classify_tool_error("网络接收错误") == "network"
    assert classify_tool_error("参数错误") == "invalid_parameters"
    assert classify_tool_error("正常数据") is None
