import pytest

from src.dialogue.graph import DialogueGraph
from src.dialogue.intent_service import ContextualIntentService
from src.dialogue.models import DialogueTaskState


@pytest.mark.asyncio
async def test_dialogue_graph_uses_thread_scoped_checkpoints_and_previous_state():
    graph = DialogueGraph(ContextualIntentService(use_llm=False))
    first_state = DialogueTaskState(session_id="thread-a")

    _, updated = await graph.resolve(
        session_id="thread-a",
        query="分析贵州茅台(600519)基本面",
        previous=first_state,
    )
    turn, second = await graph.resolve(
        session_id="thread-a",
        query="那它估值高吗",
        previous=updated,
    )

    assert turn.intent_change == "refine"
    assert [stock.code for stock in second.tickers] == ["sh.600519"]
    assert [item.value for item in second.analysis_dimensions] == ["value"]
    assert second.state_version == 2

