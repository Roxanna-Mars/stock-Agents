import pytest

from src.orchestration.roles import ResearchRole, ToolAccessController


def test_data_and_modeling_roles_have_separated_tool_permissions():
    access = ToolAccessController()

    assert access.is_allowed(ResearchRole.DATA, "mcp.get_stock_data") is True
    assert access.is_allowed(ResearchRole.DATA, "compute.dcf") is False
    assert access.is_allowed(ResearchRole.MODELING, "compute.dcf") is True
    assert access.is_allowed(ResearchRole.REPORT, "mcp.get_stock_data") is False


def test_compute_operator_allowlist_is_enforced():
    access = ToolAccessController()

    access.require_compute_operator(ResearchRole.MODELING, "dcf")
    with pytest.raises(PermissionError, match="ddm"):
        access.require_compute_operator(ResearchRole.MODELING, "ddm")
    with pytest.raises(PermissionError, match="lead"):
        access.require_allowed(ResearchRole.LEAD, "mcp.get_stock_data")
