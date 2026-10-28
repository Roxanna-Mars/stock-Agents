"""Cross-check LLM claims against deterministic data and calculation artifacts."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from src.domain.models import (
    ArtifactKind,
    AuditFinding,
    AuditSeverity,
    AuditStatus,
    CalculationArtifact,
    Claim,
    DataArtifact,
    ResearchArtifact,
    StrictModel,
    stable_content_hash,
)
from src.provenance.ledger import ProvenanceLedger


class AuditReport(StrictModel):
    status: AuditStatus
    findings: list[AuditFinding] = Field(default_factory=list)
    checked_records: int = 0
    checked_claims: int = 0


class AuditEngine:
    def __init__(self, *, relative_tolerance: float = 0.005, absolute_tolerance: float = 1e-6) -> None:
        if relative_tolerance < 0 or absolute_tolerance < 0:
            raise ValueError("audit tolerances must be non-negative")
        self.relative_tolerance = relative_tolerance
        self.absolute_tolerance = absolute_tolerance

    def audit(
        self,
        ledger: ProvenanceLedger,
        *,
        claims: list[Claim] | None = None,
        research_artifact: ResearchArtifact | None = None,
    ) -> AuditReport:
        records = ledger.records()
        findings: list[AuditFinding] = []
        effective_claims = claims or [item for item in records if isinstance(item, Claim)]

        for record in records:
            if isinstance(record, DataArtifact):
                findings.extend(self._audit_data(record))
            elif isinstance(record, CalculationArtifact):
                findings.extend(self._audit_calculation(record, ledger))

        for claim in effective_claims:
            findings.extend(self._audit_claim(claim, ledger))

        if research_artifact is not None:
            findings.extend(self._audit_research_artifact(research_artifact, ledger))

        status = AuditStatus.PASS
        if any(finding.status == AuditStatus.FAIL for finding in findings):
            status = AuditStatus.FAIL
        elif any(finding.status == AuditStatus.WARN for finding in findings):
            status = AuditStatus.WARN
        return AuditReport(
            status=status,
            findings=findings,
            checked_records=len(records),
            checked_claims=len(effective_claims),
        )

    def _finding(
        self,
        *,
        check_name: str,
        status: AuditStatus,
        severity: AuditSeverity,
        message: str,
        claim_id: str | None = None,
        references: list[str] | None = None,
        expected: Any = None,
        actual: Any = None,
    ) -> AuditFinding:
        fingerprint = stable_content_hash(
            [check_name, status.value, message, claim_id, references, expected, actual]
        )[:16].upper()
        return AuditFinding(
            finding_id=f"A-{fingerprint}",
            check_name=check_name,
            severity=severity,
            status=status,
            message=message,
            claim_id=claim_id,
            references=references or [],
            expected=expected,
            actual=actual,
        )

    def _audit_data(self, artifact: DataArtifact) -> list[AuditFinding]:
        findings: list[AuditFinding] = []
        if not artifact.is_point_in_time_safe:
            findings.append(
                self._finding(
                    check_name="point_in_time",
                    status=AuditStatus.FAIL,
                    severity=AuditSeverity.ERROR,
                    message=f"{artifact.artifact_id} was published after its as_of date",
                    references=[artifact.artifact_id],
                    expected=f"published_at <= {artifact.as_of.isoformat()}",
                    actual=artifact.published_at,
                )
            )
        if artifact.stale:
            findings.append(
                self._finding(
                    check_name="data_freshness",
                    status=AuditStatus.WARN,
                    severity=AuditSeverity.WARNING,
                    message=f"{artifact.artifact_id} is marked stale",
                    references=[artifact.artifact_id],
                )
            )
        return findings

    def _audit_calculation(
        self,
        calculation: CalculationArtifact,
        ledger: ProvenanceLedger,
    ) -> list[AuditFinding]:
        missing = ledger.missing_references(calculation.input_refs)
        if not missing:
            return []
        return [
            self._finding(
                check_name="calculation_input_references",
                status=AuditStatus.FAIL,
                severity=AuditSeverity.ERROR,
                message=f"{calculation.calculation_id} has missing input references: {missing}",
                references=calculation.input_refs,
                expected="all calculation inputs present in provenance ledger",
                actual=missing,
            )
        ]

    def _audit_claim(
        self,
        claim: Claim,
        ledger: ProvenanceLedger,
    ) -> list[AuditFinding]:
        findings: list[AuditFinding] = []
        missing = ledger.missing_references(claim.references)
        if missing:
            findings.append(
                self._finding(
                    check_name="claim_references",
                    status=AuditStatus.FAIL,
                    severity=AuditSeverity.ERROR,
                    message=f"claim {claim.claim_id} cites missing records: {missing}",
                    claim_id=claim.claim_id,
                    references=claim.references,
                    expected="all claim references present in provenance ledger",
                    actual=missing,
                )
            )
            return findings

        if claim.claim_type != "numeric":
            return findings
        actual = self._to_number(claim.value)
        if actual is None or not claim.metric:
            findings.append(
                self._finding(
                    check_name="numeric_claim_shape",
                    status=AuditStatus.WARN,
                    severity=AuditSeverity.WARNING,
                    message=f"numeric claim {claim.claim_id} lacks a numeric value or metric",
                    claim_id=claim.claim_id,
                    references=claim.references,
                )
            )
            return findings

        expected_values = []
        for reference in claim.references:
            record = ledger.get(reference)
            if isinstance(record, CalculationArtifact) and claim.metric in record.result:
                expected = self._to_number(record.result[claim.metric])
                if expected is not None:
                    expected_values.append((reference, expected))
        if not expected_values:
            findings.append(
                self._finding(
                    check_name="numeric_claim_grounding",
                    status=AuditStatus.WARN,
                    severity=AuditSeverity.WARNING,
                    message=(
                        f"numeric claim {claim.claim_id} has no referenced calculation "
                        f"containing metric {claim.metric!r}"
                    ),
                    claim_id=claim.claim_id,
                    references=claim.references,
                )
            )
            return findings

        reference, expected = expected_values[0]
        tolerance = max(
            self.absolute_tolerance,
            self.relative_tolerance * max(abs(expected), 1.0),
        )
        matches = abs(actual - expected) <= tolerance
        findings.append(
            self._finding(
                check_name="numeric_claim_consistency",
                status=AuditStatus.PASS if matches else AuditStatus.FAIL,
                severity=AuditSeverity.INFO if matches else AuditSeverity.ERROR,
                message=(
                    f"claim {claim.claim_id} matches {reference}"
                    if matches
                    else f"claim {claim.claim_id} conflicts with {reference}"
                ),
                claim_id=claim.claim_id,
                references=[reference],
                expected=expected,
                actual=actual,
            )
        )
        return findings

    def _audit_research_artifact(
        self,
        artifact: ResearchArtifact,
        ledger: ProvenanceLedger,
    ) -> list[AuditFinding]:
        references = artifact.data_refs + artifact.calculation_refs + artifact.claim_refs
        missing = ledger.missing_references(references)
        if not missing:
            return []
        return [
            self._finding(
                check_name="report_references",
                status=AuditStatus.FAIL,
                severity=AuditSeverity.ERROR,
                message=f"report artifact cites missing records: {missing}",
                references=references,
                expected="all report references present in provenance ledger",
                actual=missing,
            )
        ]

    @staticmethod
    def _to_number(value: Any) -> float | None:
        if isinstance(value, bool) or value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(str(value).replace(",", "").strip())
        except ValueError:
            return None
