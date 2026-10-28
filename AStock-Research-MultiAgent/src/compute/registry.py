"""Explicit registry for deterministic financial operators."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from src.domain.models import CalculationArtifact


Operator = Callable[..., CalculationArtifact]


class UnknownOperatorError(KeyError):
    pass


class ComputeEngine:
    def __init__(self) -> None:
        self._operators: dict[str, Operator] = {}

    def register(self, name: str, operator: Operator) -> None:
        normalized = name.strip().casefold()
        if not normalized:
            raise ValueError("operator name must not be blank")
        if normalized in self._operators:
            raise ValueError(f"operator {normalized!r} is already registered")
        self._operators[normalized] = operator

    def available_operators(self) -> tuple[str, ...]:
        return tuple(sorted(self._operators))

    def execute(self, name: str, **inputs: Any) -> CalculationArtifact:
        normalized = name.strip().casefold()
        try:
            operator = self._operators[normalized]
        except KeyError as error:
            raise UnknownOperatorError(normalized) from error
        return operator(**inputs)

    @classmethod
    def with_builtin_operators(cls) -> "ComputeEngine":
        from src.compute.operators.dcf import calculate_dcf
        from src.compute.operators.monte_carlo import calculate_dcf_monte_carlo
        from src.compute.operators.multiples import calculate_multiples_valuation

        engine = cls()
        engine.register("dcf", calculate_dcf)
        engine.register("multiples", calculate_multiples_valuation)
        engine.register("monte_carlo_dcf", calculate_dcf_monte_carlo)
        return engine
