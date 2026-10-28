"""Compatibility adapters from the current dictionary-based workflow."""

from __future__ import annotations

from datetime import date
from typing import Any, Mapping

from src.domain.models import (
    Market,
    PlanStep,
    ResearchPlan,
    ResearchRequest,
    TaskType,
    stable_content_hash,
)


def research_request_from_legacy_data(data: Mapping[str, Any]) -> ResearchRequest:
    """Build a typed request from the existing ``AgentState['data']`` payload."""
    task_value = str(data.get("task_type") or TaskType.COMPREHENSIVE_ANALYSIS.value)
    try:
        task_type = TaskType(task_value)
    except ValueError:
        task_type = TaskType.COMPREHENSIVE_ANALYSIS

    stocks = data.get("stocks") or []
    symbols = [
        str(stock.get("stock_code"))
        for stock in stocks
        if isinstance(stock, Mapping) and stock.get("stock_code")
    ]
    if not symbols and data.get("stock_code"):
        symbols = [str(data["stock_code"])]

    as_of_value = data.get("current_date") or date.today().isoformat()
    return ResearchRequest(
        query=str(data.get("query") or "Legacy financial research request"),
        symbols=symbols,
        market=Market.CN,
        as_of=date.fromisoformat(str(as_of_value)),
        task_type=task_type,
    )


def research_plan_from_legacy_task_plan(
    request: ResearchRequest,
    task_plan: Mapping[str, Any],
) -> ResearchPlan:
    """Translate the deterministic planner output into the new plan contract."""
    agent_steps = []
    for agent_name in task_plan.get("requested_agents") or []:
        agent_steps.append(
            PlanStep(
                step_id=f"analyze-{agent_name}",
                role=f"{agent_name}_agent",
                action=f"Run legacy {agent_name} analysis",
            )
        )

    dependencies = [step.step_id for step in agent_steps]
    if dependencies:
        agent_steps.append(
            PlanStep(
                step_id="synthesize-report",
                role="summary_agent",
                action="Synthesize legacy agent outputs into a report",
                depends_on=dependencies,
            )
        )

    fingerprint = stable_content_hash(
        {
            "query": request.query,
            "symbols": request.symbols,
            "task_plan": dict(task_plan),
        }
    )[:12]
    return ResearchPlan(
        plan_id=f"PLAN-{fingerprint.upper()}",
        request=request,
        playbook_id=f"legacy-{task_plan.get('task_type', 'analysis')}",
        steps=agent_steps,
    )
