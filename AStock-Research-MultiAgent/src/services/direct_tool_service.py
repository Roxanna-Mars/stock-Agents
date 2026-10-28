"""Execute an allowlisted factual query with exactly one MCP tool call."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from src.planning.direct_tool_planner import DirectToolPlan
from src.tools.mcp_client import get_mcp_tools
from src.utils.execution_logger import (
    EventSink,
    finalize_execution_logger,
    initialize_execution_logger,
)
from src.utils.tool_result_utils import classify_tool_error
from src.utils.trace_context import bind_agent_trace


@dataclass(frozen=True)
class DirectToolRunResult:
    execution_id: str
    report: str
    report_path: None
    duration_seconds: float
    task_plan: dict[str, Any]
    final_state: dict[str, Any]
    warnings: tuple[str, ...]


class DirectToolService:
    def __init__(
        self,
        *,
        log_dir: str | Path = "logs",
        timezone_name: str = "Asia/Shanghai",
    ) -> None:
        self.log_dir = Path(log_dir)
        self.timezone = ZoneInfo(timezone_name)

    async def run(
        self,
        plan: DirectToolPlan,
        *,
        event_sink: EventSink | None = None,
    ) -> DirectToolRunResult:
        started = time.perf_counter()
        execution_logger = initialize_execution_logger(
            str(self.log_dir),
            event_sink=event_sink,
        )
        execution_logger.emit_event(
            "workflow.planned",
            {
                "task_type": "fact_query",
                "execution_route": "direct_tool",
                "selected_agents": [],
                "selected_tool": plan.tool_name,
                "fact_kind": plan.fact_kind,
                "stocks": [
                    {
                        "company_name": plan.company_name,
                        "stock_code": plan.stock_code,
                    }
                ] if plan.stock_code else [],
            },
        )
        execution_logger.log_agent_start(
            "direct_tool",
            {"tool_name": plan.tool_name, "arguments": plan.arguments},
        )
        try:
            tools = await get_mcp_tools()
            selected = next(
                (tool for tool in tools if getattr(tool, "name", None) == plan.tool_name),
                None,
            )
            if selected is None:
                raise RuntimeError(f"MCP tool is unavailable: {plan.tool_name}")

            with bind_agent_trace("direct_tool"):
                raw_result = await selected.ainvoke(plan.arguments)
            result = self._normalize_result(raw_result)
            error_type = classify_tool_error(result)
            if error_type is not None:
                raise RuntimeError(f"Direct tool failed ({error_type}): {result[:500]}")

            report = self._format_report(plan, result)
            duration = time.perf_counter() - started
            execution_logger.log_agent_complete(
                "direct_tool",
                {"tool_name": plan.tool_name, "report_generated": True},
                duration,
                success=True,
            )
            execution_logger.log_final_report(report, "")
            execution_id = execution_logger.execution_id
            finalize_execution_logger(success=True)
            task_plan = {
                "task_type": "fact_query",
                "execution_route": "direct_tool",
                "direct_tool": plan.public_metadata(),
            }
            return DirectToolRunResult(
                execution_id=execution_id,
                report=report,
                report_path=None,
                duration_seconds=duration,
                task_plan=task_plan,
                final_state={"data": {"final_report": report, "task_plan": task_plan}},
                warnings=(),
            )
        except asyncio.CancelledError:
            duration = time.perf_counter() - started
            message = "Direct tool query cancelled by user"
            execution_logger.log_agent_complete(
                "direct_tool",
                {"tool_name": plan.tool_name},
                duration,
                success=False,
                error=message,
            )
            execution_logger.emit_event(
                "workflow.cancelled",
                {"reason": "user_requested", "duration_seconds": duration},
            )
            finalize_execution_logger(success=False, error=message)
            raise
        except Exception as error:
            duration = time.perf_counter() - started
            execution_logger.log_agent_complete(
                "direct_tool",
                {"tool_name": plan.tool_name},
                duration,
                success=False,
                error=str(error),
            )
            finalize_execution_logger(success=False, error=str(error))
            raise

    @staticmethod
    def _normalize_result(result: Any) -> str:
        if isinstance(result, tuple) and result:
            result = result[0]
        if isinstance(result, dict) and "content" in result:
            result = result["content"]
        return str(result).strip()

    def _format_report(self, plan: DirectToolPlan, result: str) -> str:
        subject = plan.company_name or plan.stock_code or "市场"
        queried_at = datetime.now(self.timezone).strftime("%Y-%m-%d %H:%M:%S")
        return (
            f"# {subject}事实查询\n\n"
            f"## 查询结果\n\n{result}\n\n"
            "## 数据来源\n\n"
            f"- MCP 工具：`{plan.tool_name}`\n"
            f"- 执行方式：直接工具调用（未启动研究 Agent 或总结 Agent）\n"
            f"- 查询时间：{queried_at}（Asia/Shanghai）\n"
        )
