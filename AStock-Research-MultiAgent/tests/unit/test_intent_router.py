import pytest

from web.backend.app.intent_router import IntentRouter


@pytest.mark.asyncio
async def test_intent_router_deterministic_fallback_preserves_legacy_execution():
    router = IntentRouter(use_llm=False)

    intent = await router.parse("比较贵州茅台(600519)和五粮液(000858)的估值")

    assert intent.task_type == "multi_stock_comparison"
    assert intent.suggested_route == "multi_agent"
    assert intent.execution_route == "legacy_workflow"
    assert [stock.code for stock in intent.stocks] == ["sh.600519", "sz.000858"]
    assert intent.source == "deterministic_fallback"
