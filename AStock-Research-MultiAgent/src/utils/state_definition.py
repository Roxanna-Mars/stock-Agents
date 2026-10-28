from __future__ import annotations

from typing import TypedDict, Sequence, Dict, Any, Annotated
from langchain_core.messages import BaseMessage
import operator

from src.domain.models import (
    AuditFinding,
    CalculationArtifact,
    Claim,
    DataArtifact,
    ResearchArtifact,
    ResearchPlan,
    ResearchRequest,
)


def merge_dicts(d1: Dict[str, Any], d2: Dict[str, Any]) -> Dict[str, Any]:
    """Merge two dictionaries, d2 values overwrite d1."""
    return {**d1, **d2}


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    data: Annotated[Dict[str, Any], merge_dicts]
    metadata: Annotated[Dict[str, Any], merge_dicts]
    evidence: Annotated[list[Dict[str, Any]], operator.add]
    # Potentially add a field for the initial user query if it needs to be passed around
    # user_query: str


class ResearchState(AgentState, total=False):
    """Typed migration target layered on top of the current state contract.

    All new fields are optional, so existing graphs can keep constructing and
    merging ``AgentState`` exactly as before while new nodes adopt typed
    artifacts incrementally.
    """

    request: ResearchRequest
    plan: ResearchPlan
    data_artifacts: Annotated[list[DataArtifact], operator.add]
    calculation_artifacts: Annotated[list[CalculationArtifact], operator.add]
    claims: Annotated[list[Claim], operator.add]
    audit_findings: list[AuditFinding]
    audit_history: Annotated[list[AuditFinding], operator.add]
    research_artifact: ResearchArtifact
    draft_report: str
    final_report: str
