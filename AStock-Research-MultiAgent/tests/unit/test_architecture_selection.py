import pytest

from src.planning.query_planner import select_architecture_agents


def test_architecture_variants_select_controlled_agent_sets():
    requested = ["technical"]

    assert select_architecture_agents(requested, "react_multi_agent") == ["technical"]
    assert select_architecture_agents(requested, "single_agent") == ["single"]
    assert select_architecture_agents(requested, "fixed_workflow") == [
        "fundamental",
        "technical",
        "value",
        "news",
    ]


def test_unknown_architecture_is_rejected():
    with pytest.raises(ValueError, match="Unsupported architecture"):
        select_architecture_agents(["technical"], "unknown")
