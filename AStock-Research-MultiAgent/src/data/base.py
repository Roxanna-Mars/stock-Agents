"""Contracts implemented by all financial data providers."""

from __future__ import annotations

from datetime import date
from typing import Any, Protocol, runtime_checkable

from pydantic import Field

from src.domain.models import DataArtifact, StrictModel


class DataQuery(StrictModel):
    data_type: str = Field(min_length=1)
    as_of: date
    symbol: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


@runtime_checkable
class DataProvider(Protocol):
    """Minimal async interface for yfinance, SEC, FMP, Finnhub or MCP."""

    name: str
    supported_data_types: frozenset[str]

    async def fetch(self, query: DataQuery) -> DataArtifact:
        """Return one normalized, provenance-ready data artifact."""
        ...
