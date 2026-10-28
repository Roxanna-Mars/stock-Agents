"""Central role and tool-access policy definitions."""

from __future__ import annotations

from enum import Enum
from fnmatch import fnmatchcase

from pydantic import Field

from src.domain.models import StrictModel


class ResearchRole(str, Enum):
    LEAD = "lead"
    DATA = "data"
    ANALYSIS = "analysis"
    MODELING = "modeling"
    BULL = "bull"
    BEAR = "bear"
    JUDGE = "judge"
    SYNTHESIS = "synthesis"
    REPORT = "report"
    AUDIT = "audit"


class RolePolicy(StrictModel):
    role: ResearchRole
    responsibility: str = Field(min_length=1)
    allowed_tools: list[str] = Field(default_factory=list)
    allowed_compute_operators: list[str] = Field(default_factory=list)
    max_tool_calls: int = Field(default=0, ge=0)


def default_role_policies() -> dict[ResearchRole, RolePolicy]:
    definitions = (
        RolePolicy(
            role=ResearchRole.LEAD,
            responsibility="Clarify scope, select a playbook and create the research plan.",
        ),
        RolePolicy(
            role=ResearchRole.DATA,
            responsibility="Acquire normalized point-in-time data and record provenance.",
            allowed_tools=["data.*", "mcp.*"],
            max_tool_calls=30,
        ),
        RolePolicy(
            role=ResearchRole.ANALYSIS,
            responsibility="Interpret supplied data artifacts without inventing numeric inputs.",
            allowed_tools=["provenance.read"],
            max_tool_calls=5,
        ),
        RolePolicy(
            role=ResearchRole.MODELING,
            responsibility="Run deterministic valuation and risk calculations.",
            allowed_tools=["provenance.read", "compute.*"],
            allowed_compute_operators=["dcf", "multiples", "monte_carlo_dcf"],
            max_tool_calls=12,
        ),
        RolePolicy(
            role=ResearchRole.BULL,
            responsibility="Build the strongest evidence-grounded upside case.",
            allowed_tools=["provenance.read"],
            max_tool_calls=3,
        ),
        RolePolicy(
            role=ResearchRole.BEAR,
            responsibility="Build the strongest evidence-grounded downside case.",
            allowed_tools=["provenance.read"],
            max_tool_calls=3,
        ),
        RolePolicy(
            role=ResearchRole.JUDGE,
            responsibility="Resolve bull/bear disagreements against evidence and assumptions.",
            allowed_tools=["provenance.read"],
            max_tool_calls=3,
        ),
        RolePolicy(
            role=ResearchRole.SYNTHESIS,
            responsibility="Combine analysis and debate into supported claims.",
            allowed_tools=["provenance.read"],
            max_tool_calls=3,
        ),
        RolePolicy(
            role=ResearchRole.REPORT,
            responsibility="Render claims and artifacts into a structured report.",
            allowed_tools=["provenance.read"],
            max_tool_calls=2,
        ),
        RolePolicy(
            role=ResearchRole.AUDIT,
            responsibility="Verify references, dates and numeric consistency before release.",
            allowed_tools=["provenance.read", "audit.*"],
            max_tool_calls=5,
        ),
    )
    return {policy.role: policy for policy in definitions}


class ToolAccessController:
    def __init__(self, policies: dict[ResearchRole, RolePolicy] | None = None) -> None:
        self.policies = policies or default_role_policies()

    def is_allowed(self, role: ResearchRole, tool_name: str) -> bool:
        policy = self.policies[role]
        return any(fnmatchcase(tool_name, pattern) for pattern in policy.allowed_tools)

    def require_allowed(self, role: ResearchRole, tool_name: str) -> None:
        if not self.is_allowed(role, tool_name):
            raise PermissionError(f"role {role.value!r} may not call tool {tool_name!r}")

    def require_compute_operator(self, role: ResearchRole, operator: str) -> None:
        policy = self.policies[role]
        if operator not in policy.allowed_compute_operators:
            raise PermissionError(
                f"role {role.value!r} may not execute compute operator {operator!r}"
            )
