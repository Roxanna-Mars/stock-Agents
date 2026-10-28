from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from src.domain.adapters import (
    research_plan_from_legacy_task_plan,
    research_request_from_legacy_data,
)
from src.domain.models import DataArtifact, PlanStep, ResearchPlan, ResearchRequest


def test_data_artifact_hash_and_point_in_time_check():
    artifact = DataArtifact.create(
        artifact_id="D-PRICE-1",
        symbol="sh.600519",
        data_type="daily_price",
        provider="baostock",
        as_of=date(2026, 10, 24),
        published_at=datetime(2026, 10, 25, tzinfo=timezone.utc),
        payload={"close": 1500.0},
    )

    assert len(artifact.payload_hash) == 64
    assert artifact.is_point_in_time_safe is False


def test_research_plan_rejects_unknown_dependency():
    request = ResearchRequest(query="分析贵州茅台", as_of=date(2026, 10, 24))

    with pytest.raises(ValidationError, match="depends on unknown steps"):
        ResearchPlan(
            plan_id="PLAN-1",
            request=request,
            playbook_id="equity-research",
            steps=[
                PlanStep(
                    step_id="report",
                    role="report_agent",
                    action="write report",
                    depends_on=["missing-analysis"],
                )
            ],
        )


def test_research_plan_rejects_dependency_cycle():
    request = ResearchRequest(query="分析贵州茅台", as_of=date(2026, 10, 24))

    with pytest.raises(ValidationError, match="dependency cycle"):
        ResearchPlan(
            plan_id="PLAN-CYCLE",
            request=request,
            playbook_id="equity-research",
            steps=[
                PlanStep(
                    step_id="analysis",
                    role="analysis_agent",
                    action="analyze",
                    depends_on=["report"],
                ),
                PlanStep(
                    step_id="report",
                    role="report_agent",
                    action="write",
                    depends_on=["analysis"],
                ),
            ],
        )


def test_legacy_adapters_create_typed_request_and_plan():
    request = research_request_from_legacy_data(
        {
            "query": "比较贵州茅台与五粮液",
            "current_date": "2026-10-24",
            "stocks": [
                {"stock_code": "sh.600519"},
                {"stock_code": "sz.000858"},
            ],
            "task_type": "multi_stock_comparison",
        }
    )
    plan = research_plan_from_legacy_task_plan(
        request,
        {
            "task_type": "multi_stock_comparison",
            "requested_agents": ["fundamental", "technical", "value"],
        },
    )

    assert request.symbols == ["sh.600519", "sz.000858"]
    assert [step.step_id for step in plan.steps][-1] == "synthesize-report"
    assert plan.steps[-1].depends_on == [
        "analyze-fundamental",
        "analyze-technical",
        "analyze-value",
    ]
