import pytest

from src.compute.operators.dcf import calculate_dcf
from src.compute.operators.monte_carlo import calculate_dcf_monte_carlo
from src.compute.registry import ComputeEngine, UnknownOperatorError


def test_dcf_produces_known_value_and_auditable_formula():
    result = calculate_dcf(
        free_cash_flows=[100.0],
        discount_rate=0.10,
        terminal_growth_rate=0.0,
        shares_outstanding=10.0,
        input_refs=["D-CASH-FLOW-1"],
    )

    assert result.result["enterprise_value"] == pytest.approx(1000.0)
    assert result.result["value_per_share"] == pytest.approx(100.0)
    assert result.input_refs == ["D-CASH-FLOW-1"]
    assert "WACC" in result.formula


def test_builtin_compute_engine_executes_multiples_and_rejects_unknown():
    engine = ComputeEngine.with_builtin_operators()
    result = engine.execute(
        "multiples",
        subject_metric=100.0,
        peer_multiples=[8.0, 10.0, 12.0],
        net_debt=200.0,
        shares_outstanding=10.0,
    )

    assert result.result["selected_multiple"] == 10.0
    assert result.result["value_per_share"] == 80.0
    with pytest.raises(UnknownOperatorError):
        engine.execute("llm_generated_math")


def test_seeded_monte_carlo_is_reproducible():
    inputs = {
        "base_free_cash_flow": 100.0,
        "forecast_years": 5,
        "growth_mean": 0.06,
        "growth_std": 0.02,
        "discount_rate_mean": 0.10,
        "discount_rate_std": 0.01,
        "terminal_growth_mean": 0.025,
        "terminal_growth_std": 0.005,
        "shares_outstanding": 10.0,
        "simulations": 300,
        "seed": 7,
    }

    first = calculate_dcf_monte_carlo(**inputs)
    second = calculate_dcf_monte_carlo(**inputs)

    assert first.calculation_id == second.calculation_id
    assert first.result == second.result
    assert first.result["value_per_share_p10"] < first.result["value_per_share_p90"]
