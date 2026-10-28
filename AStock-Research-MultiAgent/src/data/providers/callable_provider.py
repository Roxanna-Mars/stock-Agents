"""Adapter for existing MCP tools and future SDK-backed provider functions."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from src.data.base import DataQuery
from src.domain.models import DataArtifact


Fetcher = Callable[[DataQuery], Mapping[str, Any] | Awaitable[Mapping[str, Any]]]


class CallableDataProvider:
    """Normalize an injected fetch function into the common provider protocol."""

    def __init__(
        self,
        *,
        name: str,
        supported_data_types: set[str] | frozenset[str],
        fetcher: Fetcher,
    ) -> None:
        self.name = name
        self.supported_data_types = frozenset(supported_data_types)
        self._fetcher = fetcher

    async def fetch(self, query: DataQuery) -> DataArtifact:
        raw = self._fetcher(query)
        payload = await raw if inspect.isawaitable(raw) else raw
        if not isinstance(payload, Mapping):
            raise TypeError("provider fetcher must return a mapping")
        return DataArtifact.create(
            artifact_id=str(payload.get("artifact_id") or self._artifact_id(query)),
            symbol=str(payload.get("symbol") or query.symbol or "GLOBAL"),
            data_type=query.data_type,
            provider=self.name,
            as_of=payload.get("as_of") or query.as_of,
            payload=dict(payload.get("payload") or payload),
            source_url=payload.get("source_url"),
            period_end=payload.get("period_end"),
            published_at=payload.get("published_at"),
            currency=payload.get("currency"),
            unit=payload.get("unit"),
            from_cache=bool(payload.get("from_cache", False)),
            stale=bool(payload.get("stale", False)),
            warnings=list(payload.get("warnings") or []),
        )

    def _artifact_id(self, query: DataQuery) -> str:
        symbol = (query.symbol or "GLOBAL").replace(".", "-").upper()
        data_type = query.data_type.replace("_", "-").upper()
        return f"D-{self.name.upper()}-{data_type}-{symbol}-{query.as_of.isoformat()}"
