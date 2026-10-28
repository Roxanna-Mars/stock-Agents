import asyncio
from pathlib import Path

import pytest

from src.dialogue.graph import DialogueGraph
from src.dialogue.intent_service import ContextualIntentService
from src.services.research_service import ResearchRunResult
from src.planning.direct_tool_planner import DirectToolPlanner
from src.services.direct_tool_service import DirectToolRunResult
from web.backend.app.database import Database
from web.backend.app.events import EventBroker
from web.backend.app.intent_router import IntentRouter
from web.backend.app.task_manager import TaskManager


class FakeResearchService:
    async def run(self, query, *, architecture, stock_hints, event_sink):
        event_sink(
            {
                "type": "agent.started",
                "execution_id": "exec-1",
                "timestamp": "2026-10-26T00:00:00Z",
                "payload": {"agent_name": "fundamental_agent"},
            }
        )
        return ResearchRunResult(
            execution_id="exec-1",
            report="# Verified report",
            report_path=str(Path("reports") / "report.md"),
            duration_seconds=2.5,
            task_plan={"task_type": "focused_analysis"},
            final_state={"data": {"final_report": "# Verified report"}},
            warnings=(),
        )


class CapturingResearchService:
    def __init__(self):
        self.queries = []

    async def run(self, query, *, architecture, stock_hints, event_sink):
        self.queries.append(query)
        return ResearchRunResult(
            execution_id=f"exec-{len(self.queries)}",
            report="# Contextual report",
            report_path=None,
            duration_seconds=0.1,
            task_plan={"task_type": "focused_analysis"},
            final_state={"data": {"final_report": "# Contextual report"}},
            warnings=(),
        )


class BlockingResearchService:
    def __init__(self):
        self.started = asyncio.Event()
        self.cancelled = asyncio.Event()

    async def run(self, query, *, architecture, stock_hints, event_sink):
        self.started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled.set()
            raise


class FailIfResearchRuns:
    async def run(self, *args, **kwargs):
        raise AssertionError("Research workflow must be skipped for direct facts")


class FakeDirectToolService:
    def __init__(self):
        self.plans = []

    async def run(self, plan, *, event_sink):
        self.plans.append(plan)
        event_sink(
            {
                "type": "tool.completed",
                "execution_id": "direct-1",
                "timestamp": "2026-10-27T00:00:00Z",
                "payload": {"tool_name": plan.tool_name, "success": True},
            }
        )
        return DirectToolRunResult(
            execution_id="direct-1",
            report="# Direct factual result",
            report_path=None,
            duration_seconds=0.5,
            task_plan={"task_type": "fact_query", "execution_route": "direct_tool"},
            final_state={"data": {"final_report": "# Direct factual result"}},
            warnings=(),
        )


@pytest.mark.asyncio
async def test_task_manager_persists_report_and_real_events(tmp_path):
    database = Database(tmp_path / "web.db")
    database.initialize()
    session = database.create_session()
    task, _ = database.create_task(
        session_id=session["id"],
        query="分析贵州茅台(600519)基本面",
        architecture="react_multi_agent",
        idempotency_key=None,
    )
    manager = TaskManager(
        database,
        EventBroker(),
        IntentRouter(use_llm=False),
        FakeResearchService(),
    )

    await manager._run(task["id"])

    completed = database.get_task(task["id"])
    detail = database.get_session(session["id"])
    event_types = [
        event["event_type"] for event in database.list_events(task["id"])
    ]
    assert completed["status"] == "completed"
    assert completed["report"] == "# Verified report"
    assert detail["messages"][-1]["role"] == "assistant"
    assert event_types == [
        "task.started",
        "intent.completed",
        "agent.started",
        "task.completed",
    ]


@pytest.mark.asyncio
async def test_task_manager_routes_allowlisted_fact_to_one_direct_tool(tmp_path):
    database = Database(tmp_path / "direct.db")
    database.initialize()
    session = database.create_session()
    task, _ = database.create_task(
        session_id=session["id"],
        query="查询贵州茅台(600519)基本信息",
        architecture="react_multi_agent",
        idempotency_key=None,
    )
    direct_service = FakeDirectToolService()
    manager = TaskManager(
        database,
        EventBroker(),
        IntentRouter(use_llm=False),
        FailIfResearchRuns(),
        DirectToolPlanner(),
        direct_service,
    )

    await manager._run(task["id"])

    completed = database.get_task(task["id"])
    event_types = [
        event["event_type"] for event in database.list_events(task["id"])
    ]
    assert completed["status"] == "completed"
    assert completed["intent"]["execution_route"] == "direct_tool"
    assert completed["intent"]["source"] == "deterministic_direct"
    assert completed["intent"]["parameters"]["direct_tool"]["tool_name"] == "get_stock_basic_info"
    assert len(direct_service.plans) == 1
    assert event_types == [
        "task.started",
        "intent.completed",
        "tool.completed",
        "task.completed",
    ]


@pytest.mark.asyncio
async def test_task_manager_inherits_stock_and_routes_only_current_dimension(tmp_path):
    database = Database(tmp_path / "contextual.db")
    database.initialize()
    session = database.create_session()
    research = CapturingResearchService()
    manager = TaskManager(
        database,
        EventBroker(),
        IntentRouter(use_llm=False),
        research,
        dialogue_graph=DialogueGraph(ContextualIntentService(use_llm=False)),
    )

    first, _ = database.create_task(
        session_id=session["id"],
        query="分析贵州茅台(600519)基本面",
        architecture="react_multi_agent",
        idempotency_key=None,
    )
    await manager._run(first["id"])
    manager = TaskManager(
        database,
        EventBroker(),
        IntentRouter(use_llm=False),
        research,
        dialogue_graph=DialogueGraph(ContextualIntentService(use_llm=False)),
    )
    second, _ = database.create_task(
        session_id=session["id"],
        query="那它现在估值高吗？",
        architecture="react_multi_agent",
        idempotency_key=None,
    )
    await manager._run(second["id"])

    stored = database.get_dialogue_state(session["id"])
    completed = database.get_task(second["id"])
    assert len(research.queries) == 2
    assert "贵州茅台(600519)" in research.queries[1]
    assert "分析维度：估值" in research.queries[1]
    assert completed["intent"]["intent_change"] == "refine"
    assert completed["intent"]["selected_agents"] == ["value"]
    assert stored["tickers"][0]["code"] == "sh.600519"
    assert stored["state_version"] == 4
    assert len(stored["result_refs"]) == 2


@pytest.mark.asyncio
async def test_task_manager_cancels_running_task_without_persisting_report(tmp_path):
    database = Database(tmp_path / "cancel.db")
    database.initialize()
    session = database.create_session()
    task, _ = database.create_task(
        session_id=session["id"],
        query="分析贵州茅台(600519)",
        architecture="react_multi_agent",
        idempotency_key=None,
    )
    research = BlockingResearchService()
    manager = TaskManager(
        database,
        EventBroker(),
        IntentRouter(use_llm=False),
        research,
    )

    manager.submit(task["id"])
    await asyncio.wait_for(research.started.wait(), timeout=2)
    cancelling = manager.cancel(task["id"])
    assert cancelling["status"] == "cancelling"

    await asyncio.wait_for(research.cancelled.wait(), timeout=2)
    for _ in range(20):
        if database.get_task(task["id"])["status"] == "cancelled":
            break
        await asyncio.sleep(0)

    cancelled = database.get_task(task["id"])
    detail = database.get_session(session["id"])
    event_types = [
        event["event_type"] for event in database.list_events(task["id"])
    ]
    assert cancelled["status"] == "cancelled"
    assert cancelled["report"] is None
    assert cancelled["cancel_reason"] == "Cancelled by user"
    assert [message["role"] for message in detail["messages"]] == ["user"]
    assert "task.cancellation_requested" in event_types
    assert event_types[-1] == "task.cancelled"
