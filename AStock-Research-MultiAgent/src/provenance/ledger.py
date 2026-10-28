"""In-memory and JSONL provenance ledgers.

Every data fetch, deterministic calculation, model claim, and final report can
be assigned a stable identifier and persisted as an append-only record.  The
ledger rejects an identifier being reused with different content.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable, TypeAlias

from pydantic import BaseModel

from src.domain.models import (
    CalculationArtifact,
    Claim,
    DataArtifact,
    EvidenceRecord,
    ResearchArtifact,
)


ProvenanceRecord: TypeAlias = (
    EvidenceRecord | DataArtifact | CalculationArtifact | Claim | ResearchArtifact
)

_SAFE_RUN_ID = re.compile(r"^[A-Za-z0-9_.-]+$")


def _record_id(record: ProvenanceRecord) -> str:
    for field_name in (
        "evidence_id",
        "calculation_id",
        "claim_id",
        "artifact_id",
    ):
        value = getattr(record, field_name, None)
        if value:
            return str(value)
    raise TypeError(f"Unsupported provenance record: {type(record)!r}")


class ProvenanceLedger:
    """Append-only collection with duplicate and reference validation."""

    def __init__(self, records: Iterable[ProvenanceRecord] | None = None) -> None:
        self._records: dict[str, ProvenanceRecord] = {}
        if records:
            self.extend(records)

    def append(self, record: ProvenanceRecord) -> str:
        record_id = _record_id(record)
        existing = self._records.get(record_id)
        if existing is not None:
            if existing.model_dump(mode="json") == record.model_dump(mode="json"):
                return record_id
            raise ValueError(
                f"provenance id {record_id!r} already exists with different content"
            )
        self._records[record_id] = record
        return record_id

    def extend(self, records: Iterable[ProvenanceRecord]) -> None:
        for record in records:
            self.append(record)

    def get(self, record_id: str) -> ProvenanceRecord | None:
        return self._records.get(record_id)

    def ids(self) -> set[str]:
        return set(self._records)

    def records(self) -> tuple[ProvenanceRecord, ...]:
        return tuple(self._records.values())

    def missing_references(self, references: Iterable[str]) -> list[str]:
        return sorted(set(references) - self.ids())

    def snapshot(self) -> list[dict[str, object]]:
        return [
            {
                "record_type": type(record).__name__,
                **record.model_dump(mode="json"),
            }
            for record in self._records.values()
        ]

    def __len__(self) -> int:
        return len(self._records)


class JsonlProvenanceStore:
    """Persist records as one append-only JSON object per line and run."""

    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)

    def path_for(self, run_id: str) -> Path:
        if not _SAFE_RUN_ID.fullmatch(run_id):
            raise ValueError("run_id may contain only letters, numbers, '.', '_' and '-'")
        return self.base_dir / f"{run_id}.jsonl"

    def append(self, run_id: str, record: ProvenanceRecord) -> Path:
        path = self.path_for(run_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "record_type": type(record).__name__,
            "record_id": _record_id(record),
            "record": record.model_dump(mode="json"),
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
        return path

    def load(self, run_id: str) -> list[dict[str, object]]:
        path = self.path_for(run_id)
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]
