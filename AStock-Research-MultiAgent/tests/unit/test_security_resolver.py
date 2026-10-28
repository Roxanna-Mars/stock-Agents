import pytest

from src.dialogue.models import (
    ContextualIntentResult,
    IntentChange,
    IntentType,
    StockPatch,
    StockRef,
    TaskStatePatch,
    UpdateOperation,
)
from src.dialogue.security_resolver import MCPSecurityResolver


@pytest.mark.asyncio
async def test_explicit_user_code_is_normalized_without_remote_lookup():
    result = ContextualIntentResult(
        utterance_intent=IntentType.SINGLE_STOCK_ANALYSIS,
        intent_change=IntentChange.NEW,
        state_patch=TaskStatePatch(
            tickers=StockPatch(
                operation=UpdateOperation.REPLACE,
                value=[StockRef(name="贵州茅台", code="600519")],
            )
        ),
    )

    validated = await MCPSecurityResolver().validate(
        "分析贵州茅台(600519)", result
    )

    assert validated.requires_clarification is False
    assert validated.state_patch.tickers.value[0].code == "sh.600519"


@pytest.mark.asyncio
async def test_name_without_code_requires_clarification():
    result = ContextualIntentResult(
        utterance_intent=IntentType.SINGLE_STOCK_ANALYSIS,
        intent_change=IntentChange.NEW,
        state_patch=TaskStatePatch(
            tickers=StockPatch(
                operation=UpdateOperation.REPLACE,
                value=[StockRef(name="名称存在歧义")],
            )
        ),
    )

    validated = await MCPSecurityResolver().validate("分析名称存在歧义", result)

    assert validated.requires_clarification is True
    assert "六位股票代码" in validated.clarification_question
