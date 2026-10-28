"""Comparable-company multiples valuation."""

from __future__ import annotations

from statistics import median
from typing import Iterable

from src.domain.models import CalculationArtifact, stable_content_hash


OPERATOR_VERSION = "1.0.0"


def calculate_multiples_valuation(
    *,
    subject_metric: float,
    peer_multiples: Iterable[float],
    shares_outstanding: float,
    net_debt: float = 0.0,
    multiple_name: str = "EV/EBITDA",
    currency: str = "CNY",
    input_refs: list[str] | None = None,
) -> CalculationArtifact:
    multiples = [float(value) for value in peer_multiples]
    if not multiples:
        raise ValueError("peer_multiples must not be empty")
    if any(value <= 0 for value in multiples):
        raise ValueError("peer_multiples must be positive")
    if subject_metric < 0:
        raise ValueError("subject_metric must be non-negative")
    if shares_outstanding <= 0:
        raise ValueError("shares_outstanding must be positive")

    selected_multiple = median(multiples)
    enterprise_value = subject_metric * selected_multiple
    equity_value = enterprise_value - net_debt
    value_per_share = equity_value / shares_outstanding
    assumptions = {
        "subject_metric": subject_metric,
        "peer_multiples": multiples,
        "selected_multiple": selected_multiple,
        "multiple_name": multiple_name,
        "shares_outstanding": shares_outstanding,
        "net_debt": net_debt,
    }
    fingerprint = stable_content_hash(assumptions)[:16].upper()
    return CalculationArtifact.create(
        calculation_id=f"C-MULTIPLES-{fingerprint}",
        operator="multiples",
        operator_version=OPERATOR_VERSION,
        input_refs=input_refs or [],
        assumptions=assumptions,
        formula="EV = SubjectMetric * MedianPeerMultiple; Equity = EV - NetDebt",
        result={
            "selected_multiple": selected_multiple,
            "enterprise_value": enterprise_value,
            "equity_value": equity_value,
            "value_per_share": value_per_share,
        },
        currency=currency,
        unit="caller_input_unit",
    )
