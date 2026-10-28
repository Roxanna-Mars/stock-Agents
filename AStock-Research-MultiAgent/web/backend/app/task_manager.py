"""Background task lifecycle bridging HTTP requests and the research service."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from src.dialogue.graph import DialogueGraph
from src.dialogue.models import DialogueTaskState
from src.dialogue.state_reducer import record_analysis_result
from src.planning.contextual_planner import plan_contextual_turn
from src.planning.direct_tool_planner import DirectToolPlanner
from src.services.direct_tool_service import DirectToolService
from src.services.research_service import ResearchService
from web.backend.app.database import Database, utc_now
from web.backend.app.events import EventBroker
from web.backend.app.intent_router import IntentRouter
from web.backend.app.models import IntentAnalysis, IntentStock, IntentTaskType


class TaskNotCancellableError(RuntimeError):
    """Raised when a task has already reached a non-cancelled terminal state."""


class TaskManager:
    def __init__(
        self,
        database: Database,
        broker: EventBroker,
        intent_router: IntentRouter,
        research_service: ResearchService,
        direct_tool_planner: DirectToolPlanner | None = None,
        direct_tool_service: DirectToolService | None = None,
        dialogue_graph: DialogueGraph | None = None,
    ) -> None:
        self.database = database
        self.broker = broker
        self.intent_router = intent_router
        self.research_service = research_service
        self.direct_tool_planner = direct_tool_planner
        self.direct_tool_service = direct_tool_service
        self.dialogue_graph = dialogue_graph
        self._tasks: dict[str, asyncio.Task[Any]] = {}
        self._session_locks: dict[str, asyncio.Lock] = {}

    def submit(self, task_id: str) -> None:
        task = asyncio.create_task(self._run(task_id), name=f"research-{task_id}")
        self._tasks[task_id] = task
        task.add_done_callback(
            lambda completed, current_id=task_id: self._task_done(
                current_id, completed
            )
        )

    def cancel(self, task_id: str, reason: str = "Cancelled by user") -> dict[str, Any]:
        record = self.database.get_task(task_id)
        if record["status"] in {"cancelling", "cancelled"}:
            return record
        if record["status"] in {"completed", "failed"}:
            raise TaskNotCancellableError(
                f"Task is already {record['status']} and cannot be cancelled"
            )

        record, transitioned = self.database.update_task_if_status(
            task_id,
            {"queued", "running"},
            status="cancelling",
            cancel_requested_at=utc_now(),
            cancel_reason=reason,
        )
        if not transitioned:
            if record["status"] in {"cancelling", "cancelled"}:
                return record
            raise TaskNotCancellableError(
                f"Task is already {record['status']} and cannot be cancelled"
            )

        self._append_event(
            task_id,
            "task.cancellation_requested",
            {"task_id": task_id, "status": "cancelling", "reason": reason},
        )
        running_task = self._tasks.get(task_id)
        if running_task is not None and not running_task.done():
            running_task.cancel()
        else:
            self._finalize_cancelled(task_id)
        return self.database.get_task(task_id)

    def _task_done(self, task_id: str, task: asyncio.Task[Any]) -> None:
        if self._tasks.get(task_id) is task:
            self._tasks.pop(task_id, None)
        if task.cancelled():
            self._finalize_cancelled(task_id)

    def _finalize_cancelled(self, task_id: str) -> dict[str, Any]:
        record, transitioned = self.database.update_task_if_status(
            task_id,
            {"queued", "running", "cancelling"},
            status="cancelled",
            cancelled_at=utc_now(),
            completed_at=utc_now(),
        )
        if transitioned:
            self._append_event(
                task_id,
                "task.cancelled",
                {
                    "task_id": task_id,
                    "status": "cancelled",
                    "reason": record.get("cancel_reason") or "Cancelled by user",
                },
            )
        return record

    def _append_event(
        self,
        task_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        self.database.append_event(task_id, event_type, payload)
        self.broker.publish(task_id)

    async def _run(self, task_id: str) -> None:
        try:
            task_record = self.database.get_task(task_id)
            session_lock = self._session_locks.setdefault(
                task_record["session_id"], asyncio.Lock()
            )
            async with session_lock:
                await self._run_serialized(task_id, task_record)
        except asyncio.CancelledError:
            self._finalize_cancelled(task_id)
            raise

    async def _run_serialized(
        self,
        task_id: str,
        task_record: dict[str, Any],
    ) -> None:
        started_record, started = self.database.update_task_if_status(
            task_id,
            {"queued"},
            status="running",
            started_at=utc_now(),
        )
        if not started:
            if started_record["status"] in {"cancelling", "cancelled"}:
                raise asyncio.CancelledError
            return
        self._append_event(
            task_id,
            "task.started",
            {"task_id": task_id, "status": "running"},
        )

        try:
            resolution = None
            execution_query = task_record["query"]
            if self.dialogue_graph is not None:
                stored = self.database.get_dialogue_state(task_record["session_id"])
                previous = (
                    DialogueTaskState.model_validate(stored)
                    if stored is not None
                    else DialogueTaskState(session_id=task_record["session_id"])
                )
                recent_messages = self.database.list_recent_messages(
                    task_record["session_id"],
                    limit=6,
                    exclude_task_id=task_id,
                )
                turn_intent, updated = await self.dialogue_graph.resolve(
                    session_id=task_record["session_id"],
                    query=task_record["query"],
                    previous=previous,
                    recent_messages=recent_messages,
                )
                self.database.save_dialogue_state(
                    task_record["session_id"],
                    updated.model_dump(mode="json"),
                    expected_version=previous.state_version,
                )
                resolution = plan_contextual_turn(
                    task_record["query"], turn_intent, updated
                )
                execution_query = resolution.resolved_query
                self._append_event(
                    task_id,
                    "dialogue.state.updated",
                    {
                        "intent": turn_intent.model_dump(mode="json"),
                        "active_task_id": updated.active_task_id,
                        "task_status": updated.task_status,
                        "tickers": [item.model_dump(mode="json") for item in updated.tickers],
                        "analysis_dimensions": [
                            item.value for item in updated.analysis_dimensions
                        ],
                        "state_version": updated.state_version,
                        "selected_agents": resolution.selected_agents,
                    },
                )

                if not resolution.should_execute:
                    no_execution_intent = {
                        "task_type": turn_intent.utterance_intent.value,
                        "stocks": [
                            {
                                "name": item.name,
                                "code": item.code,
                                "market": item.market,
                            }
                            for item in updated.tickers
                        ],
                        "dimensions": [
                            item.value for item in updated.analysis_dimensions
                        ],
                        "time_range": updated.time_range,
                        "parameters": {},
                        "suggested_route": "specialist_agent",
                        "confidence": turn_intent.confidence,
                        "summary": turn_intent.summary,
                        "source": turn_intent.source,
                        "fallback_reason": turn_intent.fallback_reason,
                        "utterance_intent": turn_intent.utterance_intent.value,
                        "intent_change": turn_intent.intent_change.value,
                        "state_patch": turn_intent.state_patch.model_dump(mode="json"),
                        "requires_clarification": turn_intent.requires_clarification,
                        "clarification_question": turn_intent.clarification_question,
                        "active_task_id": updated.active_task_id,
                        "dialogue_state_version": updated.state_version,
                        "selected_agents": [],
                    }
                    await self._complete_without_execution(
                        task_id,
                        task_record,
                        no_execution_intent,
                        resolution.response_message or "本轮无需执行投研工作流。",
                    )
                    return

            direct_plan = (
                self.direct_tool_planner.plan(execution_query)
                if self.direct_tool_planner is not None
                else None
            )
            if direct_plan is not None and self.direct_tool_service is not None:
                intent = IntentAnalysis(
                    task_type=IntentTaskType.FACT_QUERY,
                    stocks=[
                        IntentStock(
                            name=direct_plan.company_name,
                            code=direct_plan.stock_code,
                            market=(direct_plan.stock_code or "").split(".")[0] or None,
                        )
                    ] if direct_plan.stock_code else [],
                    dimensions=[],
                    parameters={"direct_tool": direct_plan.public_metadata()},
                    suggested_route="direct_tool",
                    execution_route="direct_tool",
                    confidence=1.0,
                    summary=direct_plan.reason,
                    source="deterministic_direct",
                )
            else:
                intent = await self.intent_router.parse(execution_query)
            intent_payload = intent.model_dump(mode="json")
            if resolution is not None:
                intent_payload.update(
                    {
                        "utterance_intent": resolution.turn_intent.utterance_intent.value,
                        "intent_change": resolution.turn_intent.intent_change.value,
                        "state_patch": resolution.turn_intent.state_patch.model_dump(mode="json"),
                        "requires_clarification": False,
                        "active_task_id": resolution.state.active_task_id,
                        "dialogue_state_version": resolution.state.state_version,
                        "resolved_query": resolution.resolved_query,
                        "selected_agents": resolution.selected_agents,
                    }
                )
            self.database.update_task(
                task_id,
                intent_json=json.dumps(intent_payload, ensure_ascii=False),
            )
            self._append_event(task_id, "intent.completed", intent_payload)

            stock_hints = [
                {
                    "company_name": stock.name,
                    "stock_code": stock.code,
                }
                for stock in intent.stocks
            ]

            def event_sink(event: dict[str, Any]) -> None:
                payload = dict(event.get("payload") or {})
                payload["execution_id"] = event.get("execution_id")
                payload["timestamp"] = event.get("timestamp")
                self._append_event(task_id, str(event["type"]), payload)

            if direct_plan is not None and self.direct_tool_service is not None:
                result = await self.direct_tool_service.run(
                    direct_plan,
                    event_sink=event_sink,
                )
            else:
                result = await self.research_service.run(
                    execution_query,
                    architecture=task_record["architecture"],
                    stock_hints=stock_hints,
                    event_sink=event_sink,
                )
            completed_at = utc_now()
            completed_record, completed = self.database.update_task_if_status(
                task_id,
                {"running"},
                status="completed",
                execution_id=result.execution_id,
                report=result.report,
                report_path=result.report_path,
                warnings_json=json.dumps(result.warnings, ensure_ascii=False),
                duration_seconds=result.duration_seconds,
                completed_at=completed_at,
            )
            if not completed:
                if completed_record["status"] in {"cancelling", "cancelled"}:
                    raise asyncio.CancelledError
                raise RuntimeError(
                    f"Task reached unexpected state: {completed_record['status']}"
                )

            if resolution is not None:
                current_state_raw = self.database.get_dialogue_state(
                    task_record["session_id"]
                )
                if current_state_raw is not None:
                    current_state = DialogueTaskState.model_validate(current_state_raw)
                    completed_state = record_analysis_result(
                        current_state,
                        execution_id=result.execution_id,
                        report_path=result.report_path,
                    )
                    self.database.save_dialogue_state(
                        task_record["session_id"],
                        completed_state.model_dump(mode="json"),
                        expected_version=current_state.state_version,
                    )
                    self._append_event(
                        task_id,
                        "dialogue.result.recorded",
                        {
                            "active_task_id": completed_state.active_task_id,
                            "state_version": completed_state.state_version,
                            "result_ref": completed_state.result_refs[-1].model_dump(mode="json")
                            if completed_state.result_refs
                            else None,
                        },
                    )
            self.database.add_message(
                task_record["session_id"],
                "assistant",
                result.report,
                {
                    "task_id": task_id,
                    "execution_id": result.execution_id,
                    "report_path": result.report_path,
                    "duration_seconds": result.duration_seconds,
                    "warnings": list(result.warnings),
                    "charts": [],
                    "execution_route": intent.execution_route,
                },
            )
            self._append_event(
                task_id,
                "task.completed",
                {
                    "task_id": task_id,
                    "status": "completed",
                    "execution_id": result.execution_id,
                    "duration_seconds": result.duration_seconds,
                    "warnings": list(result.warnings),
                    "execution_route": intent.execution_route,
                },
            )
        except Exception as error:
            message = str(error)
            failed_record, failed = self.database.update_task_if_status(
                task_id,
                {"queued", "running"},
                status="failed",
                error=message,
                completed_at=utc_now(),
            )
            if failed:
                self._append_event(
                    task_id,
                    "task.failed",
                    {"task_id": task_id, "status": "failed", "error": message},
                )
            elif failed_record["status"] in {"cancelling", "cancelled"}:
                raise asyncio.CancelledError from error

    async def _complete_without_execution(
        self,
        task_id: str,
        task_record: dict[str, Any],
        intent_payload: dict[str, Any],
        message: str,
    ) -> None:
        intent_payload = {
            **intent_payload,
            "execution_route": "none",
        }
        completed_record, completed = self.database.update_task_if_status(
            task_id,
            {"running"},
            status="completed",
            intent_json=json.dumps(intent_payload, ensure_ascii=False),
            report=message,
            warnings_json="[]",
            duration_seconds=0.0,
            completed_at=utc_now(),
        )
        if not completed:
            if completed_record["status"] in {"cancelling", "cancelled"}:
                raise asyncio.CancelledError
            raise RuntimeError(
                f"Task reached unexpected state: {completed_record['status']}"
            )
        self.database.add_message(
            task_record["session_id"],
            "assistant",
            message,
            {
                "task_id": task_id,
                "execution_route": "none",
                "requires_clarification": bool(
                    intent_payload.get("requires_clarification")
                ),
            },
        )
        self._append_event(task_id, "intent.completed", intent_payload)
        self._append_event(
            task_id,
            "task.completed",
            {
                "task_id": task_id,
                "status": "completed",
                "execution_route": "none",
            },
        )
