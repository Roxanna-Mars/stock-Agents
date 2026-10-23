"""Shared runtime limits and tool-use rules for ReAct agents."""

import os


DEFAULT_REACT_RECURSION_LIMIT = 40
MIN_REACT_RECURSION_LIMIT = 10
MAX_REACT_RECURSION_LIMIT = 64


TOOL_USAGE_RULES = """
工具调用规则：
1. 只调用完成当前分析所必需的工具，最多进行10轮工具调用。
2. 同一工具使用相同参数失败后，不得重复调用。
3. 如果工具返回“用户未登录”、“10001001”、“网络接收错误”或其他系统性错误，立即停止继续尝试同类数据工具。
4. 数据不可用时，基于已经成功取得的数据输出降级分析，并明确列出缺失数据。
5. 不得将模型记忆或估算值伪装成工具获取的实时数据。
""".strip()


def get_react_invoke_config() -> dict[str, int]:
    """Return a bounded LangGraph recursion limit from the environment."""
    raw_value = os.getenv(
        "REACT_RECURSION_LIMIT",
        str(DEFAULT_REACT_RECURSION_LIMIT),
    )

    try:
        recursion_limit = int(raw_value)
    except (TypeError, ValueError):
        recursion_limit = DEFAULT_REACT_RECURSION_LIMIT

    recursion_limit = max(
        MIN_REACT_RECURSION_LIMIT,
        min(recursion_limit, MAX_REACT_RECURSION_LIMIT),
    )
    return {"recursion_limit": recursion_limit}
