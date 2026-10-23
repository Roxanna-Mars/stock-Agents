from src.planning.query_planner import extract_stocks, plan_query


def test_comprehensive_query_selects_four_research_agents():
    plan = plan_query("分析贵州茅台(600519)")

    assert plan["task_type"] == "comprehensive_analysis"
    assert plan["requested_agents"] == [
        "fundamental",
        "technical",
        "value",
        "news",
    ]
    assert plan["stocks"] == [
        {"company_name": "贵州茅台", "stock_code": "sh.600519"}
    ]


def test_focused_query_selects_only_required_agent():
    plan = plan_query("只分析贵州茅台(600519)最近六个月的技术面，不要查询新闻")

    assert plan["task_type"] == "focused_analysis"
    assert plan["requested_agents"] == ["technical"]


def test_comparison_extracts_every_stock_and_uses_comparison_agent():
    plan = plan_query("比较贵州茅台(600519)与五粮液(000858)的盈利能力和估值")

    assert plan["task_type"] == "multi_stock_comparison"
    assert plan["requested_agents"] == ["comparison"]
    assert [stock["stock_code"] for stock in plan["stocks"]] == [
        "sh.600519",
        "sz.000858",
    ]


def test_code_only_query_is_normalized():
    assert extract_stocks("分析股票代码600519") == [
        {"company_name": None, "stock_code": "sh.600519"}
    ]


def test_financial_calculation_uses_minimum_relevant_agent_set():
    plan = plan_query("计算贵州茅台(600519)最近两年的净利率同比增长率")

    assert plan["task_type"] == "financial_calculation"
    assert plan["requested_agents"] == ["fundamental"]


def test_specialized_calculations_route_to_their_data_owners():
    roe_plan = plan_query("计算招商银行(600036)的ROE")
    dividend_plan = plan_query("计算五粮液(000858)的股息率")

    assert roe_plan["requested_agents"] == ["fundamental", "value"]
    assert dividend_plan["requested_agents"] == ["value"]


def test_invalid_code_and_missing_name_use_basic_information_lookup():
    invalid_plan = plan_query("分析不存在的股票(999999)，不要编造")
    missing_name_plan = plan_query("分析股票代码600519，但不要假设公司名称")

    assert invalid_plan["requested_agents"] == ["fundamental"]
    assert missing_name_plan["requested_agents"] == ["fundamental"]
