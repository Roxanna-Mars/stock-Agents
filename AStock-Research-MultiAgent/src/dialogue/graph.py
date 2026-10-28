"""Small LangGraph used only for dialogue understanding and state updates."""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from src.dialogue.intent_service import ContextualIntentService
from src.dialogue.models import ContextualIntentResult, DialogueTaskState
from src.dialogue.state_reducer import apply_dialogue_turn
from src.dialogue.security_resolver import SecurityResolver


class DialogueGraphState(TypedDict, total=False):
    session_id: str
    query: str
    previous_state: dict[str, Any]
    recent_messages: list[dict[str, Any]]
    turn_intent: dict[str, Any]
    updated_state: dict[str, Any]


class DialogueGraph:
    """Run context understanding and the pure reducer as two explicit nodes.

    A LangGraph checkpointer records turn snapshots by ``session_id``.  The Web
    database remains the durable projection so a process restart can seed the
    graph again without storing large reports inside checkpoints.
    """

    def __init__(
        self,
        intent_service: ContextualIntentService,
        *,
        checkpointer: Any | None = None,
        security_resolver: SecurityResolver | None = None,
    ) -> None:
        self.intent_service = intent_service
        self.checkpointer = checkpointer or MemorySaver()
        self.security_resolver = security_resolver
        builder = StateGraph(DialogueGraphState)
        builder.add_node("understand_turn", self._understand_turn)
        builder.add_node("update_dialogue_state", self._update_dialogue_state)
        builder.add_edge(START, "understand_turn")
        builder.add_edge("understand_turn", "update_dialogue_state")
        builder.add_edge("update_dialogue_state", END)
        self.app = builder.compile(checkpointer=self.checkpointer)

    async def _understand_turn(self, state: DialogueGraphState) -> dict[str, Any]:
        previous = DialogueTaskState.model_validate(state["previous_state"])
        result = await self.intent_service.parse(
            state["query"],
            previous,
            state.get("recent_messages", []),
        )
        if self.security_resolver is not None:
            result = await self.security_resolver.validate(state["query"], result)
        return {"turn_intent": result.model_dump(mode="json")}

    @staticmethod
    def _update_dialogue_state(state: DialogueGraphState) -> dict[str, Any]:
        previous = DialogueTaskState.model_validate(state["previous_state"])
        turn = ContextualIntentResult.model_validate(state["turn_intent"])
        updated = apply_dialogue_turn(previous, turn, query=state["query"])
        return {"updated_state": updated.model_dump(mode="json")}

    async def resolve(
        self,
        *,
        session_id: str,
        query: str,
        previous: DialogueTaskState,
        recent_messages: list[dict[str, Any]] | None = None,
    ) -> tuple[ContextualIntentResult, DialogueTaskState]:
        output = await self.app.ainvoke(
            {
                "session_id": session_id,
                "query": query,
                "previous_state": previous.model_dump(mode="json"),
                "recent_messages": recent_messages or [],
            },
            config={
                "configurable": {
                    "thread_id": session_id,
                    "checkpoint_ns": "dialogue-v1",
                }
            },
        )
        return (
            ContextualIntentResult.model_validate(output["turn_intent"]),
            DialogueTaskState.model_validate(output["updated_state"]),
        )
