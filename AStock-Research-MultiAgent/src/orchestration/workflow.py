"""Composable LangGraph topology for the new research platform."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

from langgraph.graph import END, StateGraph

from src.domain.models import AuditStatus
from src.utils.state_definition import ResearchState


NodeResult = Mapping[str, Any]
NodeHandler = Callable[[ResearchState], NodeResult | Awaitable[NodeResult]]


@dataclass(frozen=True)
class ResearchHandlers:
    lead: NodeHandler
    data: NodeHandler
    analysis: NodeHandler
    modeling: NodeHandler
    bull: NodeHandler
    bear: NodeHandler
    judge: NodeHandler
    synthesis: NodeHandler
    report: NodeHandler
    audit: NodeHandler


async def _invoke(handler: NodeHandler, state: ResearchState) -> dict[str, Any]:
    result = handler(state)
    if inspect.isawaitable(result):
        result = await result
    return dict(result)


def _audit_failed(state: ResearchState) -> bool:
    findings = state.get("audit_findings", [])
    return any(finding.status == AuditStatus.FAIL for finding in findings)


def build_research_workflow(
    handlers: ResearchHandlers,
    *,
    max_audit_attempts: int = 2,
):
    """Build the platform workflow without changing the legacy workflow.

    A failed audit returns to the report node while retries remain.  The audit
    wrapper owns the attempt counter so a handler cannot accidentally create an
    infinite loop by forgetting to update it.
    """
    if max_audit_attempts < 1:
        raise ValueError("max_audit_attempts must be at least 1")

    graph = StateGraph(ResearchState)
    for role in (
        "lead",
        "data",
        "analysis",
        "modeling",
        "bull",
        "bear",
        "judge",
        "synthesis",
        "report",
    ):
        handler = getattr(handlers, role)

        async def node(state: ResearchState, selected: NodeHandler = handler):
            return await _invoke(selected, state)

        graph.add_node(role, node)

    async def audit_node(state: ResearchState):
        result = await _invoke(handlers.audit, state)
        metadata = dict(state.get("metadata", {}))
        handler_metadata = dict(result.get("metadata", {}))
        handler_metadata.pop("audit_attempts", None)
        metadata.update(handler_metadata)
        previous_attempts = int(state.get("metadata", {}).get("audit_attempts", 0))
        metadata["audit_attempts"] = previous_attempts + 1
        result["metadata"] = metadata
        result["audit_history"] = list(result.get("audit_findings", []))
        return result

    graph.add_node("audit", audit_node)
    graph.set_entry_point("lead")
    graph.add_edge("lead", "data")
    graph.add_edge("data", "analysis")
    graph.add_edge("analysis", "modeling")
    graph.add_edge("modeling", "bull")
    graph.add_edge("modeling", "bear")
    graph.add_edge(["bull", "bear"], "judge")
    graph.add_edge("judge", "synthesis")
    graph.add_edge("synthesis", "report")
    graph.add_edge("report", "audit")

    def route_after_audit(state: ResearchState) -> str:
        attempts = int(state.get("metadata", {}).get("audit_attempts", 0))
        if _audit_failed(state) and attempts < max_audit_attempts:
            return "revise"
        return "finish"

    graph.add_conditional_edges(
        "audit",
        route_after_audit,
        {"revise": "report", "finish": END},
    )
    return graph.compile()
