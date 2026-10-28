from datetime import date, datetime, timezone

import pytest

from src.audit.engine import AuditEngine
from src.compute.operators.dcf import calculate_dcf
from src.domain.models import AuditStatus, Claim, DataArtifact
from src.provenance.ledger import ProvenanceLedger


def build_grounded_ledger(claim_value: float = 100.0):
    data = DataArtifact.create(
        artifact_id="D-CASH-FLOW-1",
        symbol="sh.600519",
        data_type="cash_flow_statement",
        provider="mock",
        as_of=date(2026, 10, 24),
        payload={"free_cash_flow": 100.0},
    )
    calculation = calculate_dcf(
        free_cash_flows=[100.0],
        discount_rate=0.10,
        terminal_growth_rate=0.0,
        shares_outstanding=10.0,
        input_refs=[data.artifact_id],
    )
    claim = Claim(
        claim_id="CL-VALUE-1",
        text=f"Estimated value is {claim_value} per share.",
        claim_type="numeric",
        metric="value_per_share",
        value=claim_value,
        unit="CNY/share",
        references=[calculation.calculation_id],
    )
    return ProvenanceLedger([data, calculation, claim]), claim


def test_audit_passes_grounded_numeric_claim():
    ledger, claim = build_grounded_ledger()

    report = AuditEngine().audit(ledger, claims=[claim])

    assert report.status == AuditStatus.PASS
    assert any(
        finding.check_name == "numeric_claim_consistency"
        and finding.status == AuditStatus.PASS
        for finding in report.findings
    )


def test_audit_rejects_numeric_conflict():
    ledger, claim = build_grounded_ledger(claim_value=120.0)

    report = AuditEngine().audit(ledger, claims=[claim])

    assert report.status == AuditStatus.FAIL
    conflict = next(
        finding
        for finding in report.findings
        if finding.check_name == "numeric_claim_consistency"
    )
    assert conflict.expected == pytest.approx(100.0)
    assert conflict.actual == 120.0


def test_audit_rejects_look_ahead_artifact():
    future_data = DataArtifact.create(
        artifact_id="D-FUTURE-1",
        symbol="sh.600519",
        data_type="earnings_release",
        provider="mock",
        as_of=date(2026, 10, 24),
        published_at=datetime(2026, 10, 25, tzinfo=timezone.utc),
        payload={"revenue": 100},
    )

    report = AuditEngine().audit(ProvenanceLedger([future_data]))

    assert report.status == AuditStatus.FAIL
    assert report.findings[0].check_name == "point_in_time"
