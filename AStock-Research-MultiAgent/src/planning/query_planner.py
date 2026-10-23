"""Parse stock identifiers and select the minimum useful agent set."""

from __future__ import annotations

import re
from typing import Any


VALID_ARCHITECTURES = {"single_agent", "fixed_workflow", "react_multi_agent"}


STOCK_WITH_NAME = re.compile(
    r"([\u4e00-\u9fffA-Za-z]{2,24})\s*[（(](\d{6})[)）]"
)
STOCK_CODE = re.compile(r"(?<!\d)(\d{6})(?!\d)")
LEADING_WORDS = (
    "请帮我分析一下",
    "请分析一下",
    "帮我分析一下",
    "给我分析一下",
    "比较",
    "横向比较",
    "分析一下",
    "分析",
    "只分析",
    "评估",
    "根据",
)


def normalize_stock_code(code: str) -> str:
    if code.startswith("6"):
        return f"sh.{code}"
    if code.startswith(("0", "3")):
        return f"sz.{code}"
    return code


def _clean_company_name(value: str) -> str:
    cleaned = value.strip(" ，,、和与及")
    changed = True
    while changed:
        changed = False
        for prefix in LEADING_WORDS:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip(" ，,、和与及")
                changed = True
    # A comparison separator can be captured before the next stock name.
    cleaned = re.split(r"[、,，]|(?:和|与|及)$", cleaned)[-1].strip()
    return cleaned


def extract_stocks(query: str) -> list[dict[str, str | None]]:
    stocks: list[dict[str, str | None]] = []
    seen: set[str] = set()
    for match in STOCK_WITH_NAME.finditer(query):
        company = _clean_company_name(match.group(1)) or None
        raw_code = match.group(2)
        code = normalize_stock_code(raw_code)
        if code not in seen:
            stocks.append({"company_name": company, "stock_code": code})
            seen.add(code)
    for raw_code in STOCK_CODE.findall(query):
        code = normalize_stock_code(raw_code)
        if code not in seen:
            stocks.append({"company_name": None, "stock_code": code})
            seen.add(code)
    return stocks


def plan_query(query: str) -> dict[str, Any]:
    stocks = extract_stocks(query)
    lowered = query.casefold()
    is_comparison = len(stocks) > 1 or any(
        marker in query for marker in ("比较", "对比", "横向")
    )
    is_calculation = any(
        marker in query for marker in ("计算", "公式", "核验", "同比增长率", "股息率")
    )

    dimensions: list[str] = []
    if any(marker in query for marker in ("技术", "走势", "均线", "MACD", "RSI", "支撑位")):
        dimensions.append("technical")
    news_forbidden = bool(
        re.search(r"(?:不要|无需|不需要|不查询|禁止)[^。；，,]{0,12}(?:新闻|舆情)", query)
    )
    if not news_forbidden and any(
        marker in query for marker in ("新闻", "舆情", "事件", "情绪")
    ):
        dimensions.append("news")
    if any(
        marker in query
        for marker in ("估值", "市盈率", "市净率", "股息率", "内在价值", "股东回报")
    ):
        dimensions.append("value")
    if any(
        marker in query
        for marker in (
            "基本面",
            "财务",
            "盈利",
            "营收",
            "利润",
            "成长",
            "偿债",
            "资产",
            "现金流",
            "ROE",
            "净利率",
            "毛利率",
            "同比增长率",
            "公司名称",
            "分红",
            "股东回报",
        )
    ):
        dimensions.append("fundamental")

    if is_comparison:
        task_type = "multi_stock_comparison"
        requested_agents = ["comparison"]
    else:
        if stocks and any("." not in stock["stock_code"] for stock in stocks):
            dimensions = ["fundamental"]
        if is_calculation and "股息率" in query:
            dimensions = ["value"]
        elif is_calculation and "ROE" in query:
            dimensions = ["fundamental", "value"]
        if is_calculation and not dimensions:
            dimensions = ["fundamental"]
        if not dimensions:
            dimensions = ["fundamental", "technical", "value", "news"]
        if is_calculation:
            task_type = "financial_calculation"
        elif len(dimensions) < 4:
            task_type = "focused_analysis"
        else:
            task_type = "comprehensive_analysis"
        requested_agents = [
            name for name in ("fundamental", "technical", "value", "news")
            if name in dimensions
        ]

    return {
        "task_type": task_type,
        "stocks": stocks,
        "requested_dimensions": dimensions,
        "requested_agents": requested_agents,
        "query": query,
        "normalized_query": lowered,
    }


def select_architecture_agents(
    requested_agents: list[str],
    architecture: str,
) -> list[str]:
    """Map one task plan to the research nodes used by an ablation architecture."""
    if architecture not in VALID_ARCHITECTURES:
        raise ValueError(f"Unsupported architecture: {architecture}")
    if architecture == "single_agent":
        return ["single"]
    if architecture == "fixed_workflow":
        return ["fundamental", "technical", "value", "news"]
    return list(requested_agents)
