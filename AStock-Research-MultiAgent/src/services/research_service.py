"""Reusable service wrapper around the existing LangGraph research workflow."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from src.domain.adapters import (
    research_plan_from_legacy_task_plan,
    research_request_from_legacy_data,
)
from src.planning.query_planner import (
    normalize_stock_code,
    plan_query,
    select_architecture_agents,
)
from src.utils.execution_logger import (
    EventSink,
    finalize_execution_logger,
    initialize_execution_logger,
)
from src.utils.state_definition import ResearchState


@dataclass(frozen=True)
class ResearchRunResult:
    execution_id: str
    report: str
    report_path: str | None
    duration_seconds: float
    task_plan: dict[str, Any]
    final_state: dict[str, Any]
    warnings: tuple[str, ...]


class ResearchService:
    """Prepare state, invoke the existing graph and normalize its final result."""

    def __init__(
        self,
        *,
        log_dir: str | Path = "logs",
        timezone_name: str = "Asia/Shanghai",
    ) -> None:
        self.log_dir = Path(log_dir)
        self.timezone = ZoneInfo(timezone_name)

    def prepare(
        self,
        query: str,
        *,
        architecture: str = "react_multi_agent",
        stock_hints: list[dict[str, str | None]] | None = None,
    ) -> tuple[dict[str, Any], ResearchState]:
        task_plan = plan_query(query)
        planned_stocks = list(task_plan.get("stocks") or [])
        if not planned_stocks and stock_hints:
            seen: set[str] = set()
            for hint in stock_hints:
                raw_code = str(hint.get("stock_code") or hint.get("code") or "").strip()
                if not raw_code:
                    continue
                normalized = normalize_stock_code(raw_code.split(".")[-1])
                if normalized in seen:
                    continue
                planned_stocks.append(
                    {
                        "company_name": hint.get("company_name") or hint.get("name"),
                        "stock_code": normalized,
                    }
                )
                seen.add(normalized)
            if planned_stocks:
                task_plan["stocks"] = planned_stocks

        now = datetime.now(self.timezone)
        weekday = "星期一星期二星期三星期四星期五星期六星期日"
        weekday_name = weekday[now.weekday() * 3 : now.weekday() * 3 + 3]
        current_date = now.strftime("%Y-%m-%d")
        current_date_cn = now.strftime("%Y年%m月%d日")
        current_time = now.strftime("%H:%M:%S")
        current_time_info = (
            f"{current_date_cn} ({current_date}) {weekday_name} {current_time}"
        )

        initial_data: dict[str, Any] = {
            "query": query,
            "current_date": current_date,
            "current_date_cn": current_date_cn,
            "current_time": current_time,
            "current_weekday_cn": weekday_name,
            "current_time_info": current_time_info,
            "analysis_timestamp": now.isoformat(),
            "task_plan": task_plan,
            "task_type": task_plan["task_type"],
            "architecture": architecture,
            "stocks": planned_stocks,
        }
        if planned_stocks:
            first = planned_stocks[0]
            initial_data["stock_code"] = first["stock_code"]
            if first.get("company_name"):
                initial_data["company_name"] = first["company_name"]

        typed_request = research_request_from_legacy_data(initial_data)
        typed_plan = research_plan_from_legacy_task_plan(typed_request, task_plan)
        initial_state = ResearchState(
            messages=[],
            data=initial_data,
            metadata={},
            evidence=[],
            request=typed_request,
            plan=typed_plan,
        )
        return task_plan, initial_state

    async def run(
        self,
        query: str,
        *,
        architecture: str = "react_multi_agent",
        stock_hints: list[dict[str, str | None]] | None = None,
        event_sink: EventSink | None = None,
    ) -> ResearchRunResult:
        # Lazy import avoids loading model libraries during a health check.
        from src.main import build_workflow

        started = time.perf_counter()
        execution_logger = initialize_execution_logger(
            str(self.log_dir),
            event_sink=event_sink,
        )
        execution_logger.log_agent_start(
            "main",
            {"user_query": query, "architecture": architecture},
        )
        try:
            task_plan, initial_state = self.prepare(
                query,
                architecture=architecture,
                stock_hints=stock_hints,
            )
            selected_agents = select_architecture_agents(
                task_plan["requested_agents"],
                architecture,
            )
            execution_logger.emit_event(
                "workflow.planned",
                {
                    "task_type": task_plan["task_type"],
                    "requested_dimensions": task_plan.get("requested_dimensions", []),
                    "selected_agents": selected_agents,
                    "stocks": task_plan.get("stocks", []),
                },
            )
            app = build_workflow(task_plan["requested_agents"], architecture)
            final_state = await app.ainvoke(initial_state)
            data = dict(final_state.get("data", {}))
            report = str(data.get("final_report") or "")
            report_path = data.get("report_path")
            if not report:
                raise RuntimeError("Workflow did not produce a final report")

            execution_logger.log_final_report(report, str(report_path or ""))
            duration = time.perf_counter() - started
            errors = [
                str(value)
                for key, value in data.items()
                if key.endswith("_error") and value
            ]
            execution_logger.log_agent_complete(
                "main",
                {
                    "report_generated": True,
                    "report_path": report_path,
                    "warnings": errors,
                },
                duration,
                success=True,
            )
            execution_id = execution_logger.execution_id
            finalize_execution_logger(success=True)
            return ResearchRunResult(
                execution_id=execution_id,
                report=report,
                report_path=str(report_path) if report_path else None,
                duration_seconds=duration,
                task_plan=task_plan,
                final_state=final_state,
                warnings=tuple(errors),
            )
        except asyncio.CancelledError:
            duration = time.perf_counter() - started
            message = "Workflow cancelled by user"
            execution_logger.log_agent_complete(
                "main",
                {},
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
                "main",
                {},
                duration,
                success=False,
                error=str(error),
            )
            finalize_execution_logger(success=False, error=str(error))
            raise
