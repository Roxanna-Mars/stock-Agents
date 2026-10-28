import pytest

from src.planning.direct_tool_planner import DirectToolPlan
from src.services.direct_tool_service import DirectToolService


class FakeTool:
    name = "get_stock_basic_info"

    def __init__(self):
        self.calls = []

    async def ainvoke(self, arguments):
        self.calls.append(arguments)
        return "| code | code_name |\n|---|---|\n| sh.600519 | 贵州茅台 |"


@pytest.mark.asyncio
async def test_direct_tool_service_invokes_exactly_one_tool(monkeypatch, tmp_path):
    tool = FakeTool()

    async def fake_get_tools():
        return [tool]

    monkeypatch.setattr(
        "src.services.direct_tool_service.get_mcp_tools",
        fake_get_tools,
    )
    events = []
    service = DirectToolService(log_dir=tmp_path / "logs")
    plan = DirectToolPlan(
        fact_kind="stock_basic_info",
        tool_name="get_stock_basic_info",
        arguments={"code": "sh.600519"},
        stock_code="sh.600519",
        company_name="贵州茅台",
    )

    result = await service.run(plan, event_sink=events.append)

    assert tool.calls == [{"code": "sh.600519"}]
    assert "未启动研究 Agent 或总结 Agent" in result.report
    assert result.task_plan["execution_route"] == "direct_tool"
    assert [event["type"] for event in events] == [
        "workflow.started",
        "workflow.planned",
        "agent.started",
        "agent.completed",
        "report.completed",
        "workflow.completed",
    ]
