import pytest

from src.dialogue.intent_service import ContextualIntentService
from src.dialogue.models import DialogueTaskState
from src.dialogue.state_reducer import apply_dialogue_turn
from src.planning.contextual_planner import plan_contextual_turn


@pytest.mark.asyncio
async def test_five_turn_research_context_evolves_without_stock_pollution():
    service = ContextualIntentService(use_llm=False)
    state = DialogueTaskState(session_id="session-1")

    queries = [
        "分析贵州茅台(600519)的投资价值",
        "那它现在估值高吗？",
        "和五粮液(000858)比较一下",
        "只比较基本面",
        "算了，换成宁德时代(300750)",
    ]
    states = []
    turns = []
    for query in queries:
        turn = await service.parse(query, state)
        state = apply_dialogue_turn(state, turn, query=query)
        turns.append(turn)
        states.append(state)

    assert [stock.code for stock in states[1].tickers] == ["sh.600519"]
    assert [item.value for item in states[1].analysis_dimensions] == ["value"]
    assert [stock.code for stock in states[2].tickers] == [
        "sh.600519",
        "sz.000858",
    ]
    assert states[2].overall_task_intent == "multi_stock_comparison"
    assert [item.value for item in states[3].analysis_dimensions] == ["fundamental"]
    assert [stock.code for stock in states[4].tickers] == ["sz.300750"]
    assert states[4].analysis_dimensions == []
    assert states[4].result_refs == []
    assert states[4].active_task_id != states[3].active_task_id
    assert turns[4].intent_change == "switch"


@pytest.mark.asyncio
async def test_missing_stock_requests_clarification_and_skips_agents():
    service = ContextualIntentService(use_llm=False)
    previous = DialogueTaskState(session_id="session-2")

    turn = await service.parse("分析一下基本面", previous)
    state = apply_dialogue_turn(previous, turn, query="分析一下基本面")
    resolution = plan_contextual_turn("分析一下基本面", turn, state)

    assert state.task_status == "awaiting_clarification"
    assert resolution.should_execute is False
    assert "股票" in resolution.response_message


@pytest.mark.asyncio
async def test_cancel_retains_snapshot_but_does_not_execute():
    service = ContextualIntentService(use_llm=False)
    state = DialogueTaskState(session_id="session-3")
    first = await service.parse("分析贵州茅台(600519)基本面", state)
    state = apply_dialogue_turn(state, first, query="分析贵州茅台(600519)基本面")

    cancel = await service.parse("取消当前任务", state)
    state = apply_dialogue_turn(state, cancel, query="取消当前任务")
    resolution = plan_contextual_turn("取消当前任务", cancel, state)

    assert state.task_status == "cancelled"
    assert state.task_history[-1].status == "cancelled"
    assert resolution.should_execute is False

