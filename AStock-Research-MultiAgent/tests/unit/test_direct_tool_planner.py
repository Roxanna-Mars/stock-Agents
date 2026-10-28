from datetime import datetime

from src.planning.direct_tool_planner import DirectToolPlanner


def test_direct_tool_planner_maps_allowlisted_fact_queries():
    planner = DirectToolPlanner()

    basic = planner.plan("查询贵州茅台(600519)基本信息")
    industry = planner.plan("贵州茅台(600519)属于什么行业")
    snapshot = planner.plan("贵州茅台(600519)当前PE是多少")
    dividend = planner.plan("贵州茅台(600519)2025年分红是多少")
    trading_date = planner.plan("最近交易日是什么")

    assert basic is not None and basic.tool_name == "get_stock_basic_info"
    assert basic.company_name == "贵州茅台"
    assert industry is not None and industry.tool_name == "get_stock_industry"
    assert snapshot is not None and snapshot.tool_name == "get_historical_k_data"
    assert snapshot.arguments["fields"][-3:] == ["peTTM", "pbMRQ", "psTTM"]
    assert dividend is not None and dividend.arguments["year"] == "2025"
    assert trading_date is not None and trading_date.arguments == {}


def test_direct_tool_planner_rejects_ambiguous_or_analytical_queries():
    planner = DirectToolPlanner()

    assert planner.plan("分析贵州茅台(600519)的估值水平") is None
    assert planner.plan("贵州茅台(600519)为什么下跌") is None
    assert planner.plan("比较贵州茅台(600519)和五粮液(000858)的市盈率") is None
    assert planner.plan("贵州茅台(600519)历史分红") is None
    assert planner.plan("贵州茅台属于什么行业") is None


def test_direct_tool_planner_resolves_relative_dividend_year():
    planner = DirectToolPlanner()
    plan = planner.plan("贵州茅台(600519)去年分红是多少")

    assert plan is not None
    assert plan.arguments["year"] == str(datetime.now().year - 1)
