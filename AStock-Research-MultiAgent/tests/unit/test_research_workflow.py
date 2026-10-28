import pytest

from src.domain.models import AuditFinding, AuditSeverity, AuditStatus
from src.orchestration.workflow import ResearchHandlers, build_research_workflow


def mark(role):
    def handler(state):
        if role == "judge":
            assert state["data"]["bull"] is True
            assert state["data"]["bear"] is True
        return {"data": {role: True}}

    return handler


def initial_state():
    return {"messages": [], "data": {}, "metadata": {}, "evidence": []}


@pytest.mark.asyncio
async def test_research_workflow_runs_parallel_debate_then_audit():
    handlers = ResearchHandlers(
        lead=mark("lead"),
        data=mark("data"),
        analysis=mark("analysis"),
        modeling=mark("modeling"),
        bull=mark("bull"),
        bear=mark("bear"),
        judge=mark("judge"),
        synthesis=mark("synthesis"),
        report=mark("report"),
        audit=lambda state: {"audit_findings": []},
    )
    workflow = build_research_workflow(handlers)

    result = await workflow.ainvoke(initial_state())

    assert result["data"]["report"] is True
    assert result["metadata"]["audit_attempts"] == 1


@pytest.mark.asyncio
async def test_failed_audit_revises_report_once_then_finishes():
    def report(state):
        runs = int(state.get("data", {}).get("report_runs", 0)) + 1
        return {"data": {"report_runs": runs}}

    def audit(state):
        if state["data"]["report_runs"] == 1:
            finding = AuditFinding(
                finding_id="A-FAIL-1",
                check_name="numeric_claim_consistency",
                severity=AuditSeverity.ERROR,
                status=AuditStatus.FAIL,
                message="report value conflicts with calculation",
            )
            return {
                "audit_findings": [finding],
                "metadata": {"audit_attempts": 999},
            }
        return {"audit_findings": []}

    handlers = ResearchHandlers(
        lead=mark("lead"),
        data=mark("data"),
        analysis=mark("analysis"),
        modeling=mark("modeling"),
        bull=mark("bull"),
        bear=mark("bear"),
        judge=mark("judge"),
        synthesis=mark("synthesis"),
        report=report,
        audit=audit,
    )
    workflow = build_research_workflow(handlers, max_audit_attempts=2)

    result = await workflow.ainvoke(initial_state())

    assert result["data"]["report_runs"] == 2
    assert result["metadata"]["audit_attempts"] == 2
    assert result["audit_findings"] == []
    assert len(result["audit_history"]) == 1
