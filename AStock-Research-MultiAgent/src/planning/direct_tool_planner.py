"""Conservative deterministic planner for one-tool factual queries."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from src.planning.query_planner import extract_stocks


ANALYTICAL_MARKERS = (
    "分析",
    "比较",
    "对比",
    "为什么",
    "原因",
    "趋势",
    "建议",
    "值得",
    "预测",
    "风险",
    "评估",
    "计算",
    "判断",
    "怎么看",
    "如何",
)


@dataclass(frozen=True)
class DirectToolPlan:
    fact_kind: str
    tool_name: str
    arguments: dict[str, Any]
    stock_code: str | None = None
    company_name: str | None = None
    reason: str = ""

    def public_metadata(self) -> dict[str, Any]:
        return {
            "fact_kind": self.fact_kind,
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "reason": self.reason,
        }


class DirectToolPlanner:
    """Allow only unambiguous, read-only queries with exactly one MCP call."""

    def __init__(self, *, timezone_name: str = "Asia/Shanghai") -> None:
        self.timezone = ZoneInfo(timezone_name)

    def plan(self, query: str) -> DirectToolPlan | None:
        normalized = query.strip()
        if not normalized or any(marker in normalized for marker in ANALYTICAL_MARKERS):
            return None

        stocks = extract_stocks(normalized)
        if any(marker in normalized for marker in ("最近交易日", "最新交易日")):
            if stocks:
                return None
            return DirectToolPlan(
                fact_kind="latest_trading_date",
                tool_name="get_latest_trading_date",
                arguments={},
                reason="明确查询最近交易日且不需要股票参数",
            )

        if len(stocks) != 1:
            return None
        stock = stocks[0]
        code = str(stock["stock_code"])
        company_name = stock.get("company_name")
        if company_name:
            company_name = re.sub(r"^(?:请)?查询", "", company_name).strip() or None

        if any(
            marker in normalized
            for marker in ("基本信息", "上市日期", "什么时候上市", "公司名称")
        ):
            return DirectToolPlan(
                fact_kind="stock_basic_info",
                tool_name="get_stock_basic_info",
                arguments={"code": code},
                stock_code=code,
                company_name=company_name,
                reason="单只股票的基本资料查询",
            )

        if any(marker in normalized for marker in ("所属行业", "什么行业", "行业分类")):
            return DirectToolPlan(
                fact_kind="stock_industry",
                tool_name="get_stock_industry",
                arguments={"code": code},
                stock_code=code,
                company_name=company_name,
                reason="单只股票的行业分类查询",
            )

        if any(marker in normalized for marker in ("分红", "派息", "现金红利")):
            year = self._extract_year(normalized)
            if year is None:
                return None
            return DirectToolPlan(
                fact_kind="dividend",
                tool_name="get_dividend_data",
                arguments={"code": code, "year": str(year), "year_type": "report"},
                stock_code=code,
                company_name=company_name,
                reason="单只股票且明确年份的分红事实查询",
            )

        snapshot_markers = (
            "最新价格",
            "最新收盘价",
            "当前价格",
            "最新股价",
            "当前股价",
            "现在多少钱",
            "多少钱",
            "收盘价",
            "市盈率",
            "市净率",
            "市销率",
            "PE",
            "PB",
            "PS",
            "pe",
            "pb",
            "ps",
        )
        if any(marker in normalized for marker in snapshot_markers):
            today = datetime.now(self.timezone).date()
            start = today - timedelta(days=14)
            return DirectToolPlan(
                fact_kind="market_snapshot",
                tool_name="get_historical_k_data",
                arguments={
                    "code": code,
                    "start_date": start.isoformat(),
                    "end_date": today.isoformat(),
                    "frequency": "d",
                    "adjust_flag": "3",
                    "fields": [
                        "date",
                        "code",
                        "close",
                        "preclose",
                        "pctChg",
                        "peTTM",
                        "pbMRQ",
                        "psTTM",
                    ],
                },
                stock_code=code,
                company_name=company_name,
                reason="单只股票的近期价格或估值快照查询",
            )
        return None

    def _extract_year(self, query: str) -> int | None:
        now = datetime.now(self.timezone)
        match = re.search(r"(?<!\d)(20\d{2})(?:年)?(?!\d)", query)
        if match:
            return int(match.group(1))
        if "今年" in query:
            return now.year
        if "去年" in query:
            return now.year - 1
        return None
