"""Provider selection, fallback and batch data retrieval."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable

from src.data.base import DataProvider, DataQuery
from src.domain.models import DataArtifact


class DataAccessError(RuntimeError):
    def __init__(self, query: DataQuery, attempts: list[tuple[str, str]]) -> None:
        self.query = query
        self.attempts = attempts
        details = "; ".join(f"{provider}: {error}" for provider, error in attempts)
        super().__init__(f"no provider returned {query.data_type!r}: {details}")


class DataProviderRegistry:
    """Resolve providers by capability while preserving explicit preference order."""

    def __init__(self, providers: Iterable[DataProvider] = ()) -> None:
        self._providers: dict[str, DataProvider] = {}
        for provider in providers:
            self.register(provider)

    def register(self, provider: DataProvider) -> None:
        if provider.name in self._providers:
            raise ValueError(f"provider {provider.name!r} is already registered")
        self._providers[provider.name] = provider

    def provider_names(self, data_type: str | None = None) -> list[str]:
        if data_type is None:
            return list(self._providers)
        return [
            name
            for name, provider in self._providers.items()
            if data_type in provider.supported_data_types
        ]

    def _candidates(
        self,
        query: DataQuery,
        preferred_providers: Iterable[str] = (),
    ) -> list[DataProvider]:
        preferred = list(dict.fromkeys(preferred_providers))
        unknown = [name for name in preferred if name not in self._providers]
        if unknown:
            raise KeyError(f"unknown data providers: {unknown}")
        ordered_names = preferred + [
            name for name in self._providers if name not in preferred
        ]
        return [
            self._providers[name]
            for name in ordered_names
            if query.data_type in self._providers[name].supported_data_types
        ]

    async def fetch(
        self,
        query: DataQuery,
        preferred_providers: Iterable[str] = (),
    ) -> DataArtifact:
        attempts: list[tuple[str, str]] = []
        for provider in self._candidates(query, preferred_providers):
            try:
                artifact = await provider.fetch(query)
                if artifact.data_type != query.data_type:
                    raise ValueError(
                        f"returned data_type {artifact.data_type!r}, expected {query.data_type!r}"
                    )
                if query.symbol and artifact.symbol != query.symbol:
                    raise ValueError(
                        f"returned symbol {artifact.symbol!r}, expected {query.symbol!r}"
                    )
                if artifact.as_of > query.as_of:
                    raise ValueError("provider returned data after the requested as_of date")
                return artifact
            except Exception as error:
                attempts.append((provider.name, f"{type(error).__name__}: {error}"))
        raise DataAccessError(query, attempts)

    async def fetch_many(
        self,
        queries: Iterable[DataQuery],
        preferred_providers: Iterable[str] = (),
    ) -> list[DataArtifact]:
        """Fetch independent requirements concurrently; providers own rate limits."""
        return list(
            await asyncio.gather(
                *(
                    self.fetch(query, preferred_providers)
                    for query in queries
                )
            )
        )
