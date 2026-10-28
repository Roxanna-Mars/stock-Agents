from src.services.research_service import ResearchService


def test_research_service_prepares_existing_workflow_state(tmp_path):
    service = ResearchService(log_dir=tmp_path)

    task_plan, state = service.prepare(
        "分析贵州茅台(600519)的基本面和估值",
        architecture="react_multi_agent",
    )

    assert task_plan["stocks"][0]["stock_code"] == "sh.600519"
    assert state["data"]["stock_code"] == "sh.600519"
    assert state["request"].query.startswith("分析贵州茅台")
    assert state["plan"].steps[-1].step_id == "synthesize-report"
