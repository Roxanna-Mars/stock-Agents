from pathlib import Path

from src.domain.models import TaskType
from src.playbooks.loader import PlaybookRegistry


def test_builtin_playbooks_load_and_validate():
    playbook_dir = Path(__file__).parents[2] / "playbooks"
    registry = PlaybookRegistry()

    registry.load_directory(playbook_dir)

    assert registry.ids() == (
        "earnings-review",
        "equity-research",
        "stock-comparison",
        "valuation",
    )
    valuation = registry.get("valuation")
    assert "dcf" in valuation.compute_operators
    assert "numeric_claims_match_calculations" in valuation.quality_gates


def test_playbook_selection_uses_task_type():
    playbook_dir = Path(__file__).parents[2] / "playbooks"
    registry = PlaybookRegistry()
    registry.load_directory(playbook_dir)

    selected = registry.select_for(TaskType.MULTI_STOCK_COMPARISON)

    assert [playbook.playbook_id for playbook in selected] == ["stock-comparison"]
