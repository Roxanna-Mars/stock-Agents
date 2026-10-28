"""Seeded Monte Carlo DCF for reproducible valuation ranges."""

from __future__ import annotations

import random
from statistics import fmean

from src.domain.models import CalculationArtifact, stable_content_hash


OPERATOR_VERSION = "1.0.0"


def _percentile(sorted_values: list[float], probability: float) -> float:
    position = (len(sorted_values) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = position - lower
    return sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight


def calculate_dcf_monte_carlo(
    *,
    base_free_cash_flow: float,
    forecast_years: int,
    growth_mean: float,
    growth_std: float,
    discount_rate_mean: float,
    discount_rate_std: float,
    terminal_growth_mean: float,
    terminal_growth_std: float,
    shares_outstanding: float,
    net_debt: float = 0.0,
    simulations: int = 1000,
    seed: int = 42,
    currency: str = "CNY",
    input_refs: list[str] | None = None,
) -> CalculationArtifact:
    if forecast_years < 1:
        raise ValueError("forecast_years must be at least 1")
    if simulations < 100:
        raise ValueError("simulations must be at least 100")
    if shares_outstanding <= 0:
        raise ValueError("shares_outstanding must be positive")
    if min(growth_std, discount_rate_std, terminal_growth_std) < 0:
        raise ValueError("standard deviations must be non-negative")

    generator = random.Random(seed)
    values: list[float] = []
    rejected = 0
    for _ in range(simulations):
        growth = generator.gauss(growth_mean, growth_std)
        discount_rate = generator.gauss(discount_rate_mean, discount_rate_std)
        terminal_growth = generator.gauss(
            terminal_growth_mean,
            terminal_growth_std,
        )
        if discount_rate <= terminal_growth or discount_rate <= -1 or terminal_growth <= -1:
            rejected += 1
            continue
        cash_flow = base_free_cash_flow
        projected: list[float] = []
        for _year in range(forecast_years):
            cash_flow *= 1.0 + growth
            projected.append(cash_flow)
        discounted = sum(
            value / ((1.0 + discount_rate) ** year)
            for year, value in enumerate(projected, start=1)
        )
        terminal_value = (
            projected[-1]
            * (1.0 + terminal_growth)
            / (discount_rate - terminal_growth)
        )
        enterprise_value = discounted + terminal_value / (
            (1.0 + discount_rate) ** forecast_years
        )
        values.append((enterprise_value - net_debt) / shares_outstanding)

    if not values:
        raise ValueError("all simulations were rejected; check rate assumptions")
    values.sort()
    assumptions = {
        "base_free_cash_flow": base_free_cash_flow,
        "forecast_years": forecast_years,
        "growth_mean": growth_mean,
        "growth_std": growth_std,
        "discount_rate_mean": discount_rate_mean,
        "discount_rate_std": discount_rate_std,
        "terminal_growth_mean": terminal_growth_mean,
        "terminal_growth_std": terminal_growth_std,
        "shares_outstanding": shares_outstanding,
        "net_debt": net_debt,
        "simulations": simulations,
        "seed": seed,
    }
    fingerprint = stable_content_hash(assumptions)[:16].upper()
    return CalculationArtifact.create(
        calculation_id=f"C-MONTE-CARLO-DCF-{fingerprint}",
        operator="monte_carlo_dcf",
        operator_version=OPERATOR_VERSION,
        input_refs=input_refs or [],
        assumptions=assumptions,
        formula="Seeded simulation of explicit-growth Gordon-growth DCF",
        result={
            "value_per_share_mean": fmean(values),
            "value_per_share_p10": _percentile(values, 0.10),
            "value_per_share_p50": _percentile(values, 0.50),
            "value_per_share_p90": _percentile(values, 0.90),
            "valid_simulations": len(values),
            "rejected_simulations": rejected,
        },
        currency=currency,
        unit="per_share",
        warnings=(
            [f"{rejected} simulations rejected because discount rate <= terminal growth"]
            if rejected
            else []
        ),
    )
