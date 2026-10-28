"""Discounted-cash-flow valuation using explicit caller-supplied cash flows."""

from __future__ import annotations

from typing import Iterable

from src.domain.models import CalculationArtifact, stable_content_hash


OPERATOR_VERSION = "1.0.0"


def calculate_dcf(
    *,
    free_cash_flows: Iterable[float],
    discount_rate: float,
    terminal_growth_rate: float,
    shares_outstanding: float,
    net_debt: float = 0.0,
    currency: str = "CNY",
    input_refs: list[str] | None = None,
) -> CalculationArtifact:
    """Calculate enterprise, equity and per-share value.

    Rates are decimals (10% = 0.10). Cash flows, debt and share counts must use
    compatible units; the unit is retained in the auditable artifact.
    """
    cash_flows = [float(value) for value in free_cash_flows]
    if not cash_flows:
        raise ValueError("free_cash_flows must contain at least one forecast year")
    if discount_rate <= terminal_growth_rate:
        raise ValueError("discount_rate must be greater than terminal_growth_rate")
    if discount_rate <= -1:
        raise ValueError("discount_rate must be greater than -100%")
    if terminal_growth_rate <= -1:
        raise ValueError("terminal_growth_rate must be greater than -100%")
    if shares_outstanding <= 0:
        raise ValueError("shares_outstanding must be positive")

    discounted_cash_flows = [
        value / ((1.0 + discount_rate) ** year)
        for year, value in enumerate(cash_flows, start=1)
    ]
    terminal_value = (
        cash_flows[-1]
        * (1.0 + terminal_growth_rate)
        / (discount_rate - terminal_growth_rate)
    )
    discounted_terminal_value = terminal_value / (
        (1.0 + discount_rate) ** len(cash_flows)
    )
    enterprise_value = sum(discounted_cash_flows) + discounted_terminal_value
    equity_value = enterprise_value - net_debt
    value_per_share = equity_value / shares_outstanding

    assumptions = {
        "free_cash_flows": cash_flows,
        "discount_rate": discount_rate,
        "terminal_growth_rate": terminal_growth_rate,
        "shares_outstanding": shares_outstanding,
        "net_debt": net_debt,
    }
    fingerprint = stable_content_hash(assumptions)[:16].upper()
    return CalculationArtifact.create(
        calculation_id=f"C-DCF-{fingerprint}",
        operator="dcf",
        operator_version=OPERATOR_VERSION,
        input_refs=input_refs or [],
        assumptions=assumptions,
        formula=(
            "EV = sum(FCF_t/(1+WACC)^t) + "
            "FCF_n*(1+g)/(WACC-g)/(1+WACC)^n; Equity = EV - NetDebt"
        ),
        result={
            "discounted_cash_flows": discounted_cash_flows,
            "terminal_value": terminal_value,
            "discounted_terminal_value": discounted_terminal_value,
            "enterprise_value": enterprise_value,
            "equity_value": equity_value,
            "value_per_share": value_per_share,
        },
        currency=currency,
        unit="caller_input_unit",
    )
