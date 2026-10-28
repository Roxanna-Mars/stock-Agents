from src.domain.models import EvidenceRecord
from src.provenance.ledger import JsonlProvenanceStore, ProvenanceLedger


def make_record(content: str = "close=1500") -> EvidenceRecord:
    return EvidenceRecord.create(
        evidence_id="E-TECHNICAL-1",
        agent_name="technical_agent",
        tool_name="get_stock_data",
        tool_call_id="call-1",
        arguments={"code": "sh.600519"},
        content=content,
        success=True,
        error_type=None,
    )


def test_ledger_is_idempotent_but_rejects_id_reuse():
    record = make_record()
    ledger = ProvenanceLedger()

    ledger.append(record)
    ledger.append(record)

    assert len(ledger) == 1
    assert ledger.missing_references(["E-TECHNICAL-1", "C-MISSING-1"]) == [
        "C-MISSING-1"
    ]

    changed = make_record("close=1600")
    try:
        ledger.append(changed)
    except ValueError as error:
        assert "different content" in str(error)
    else:
        raise AssertionError("ledger accepted a conflicting record id")


def test_jsonl_store_appends_and_loads_records(tmp_path):
    store = JsonlProvenanceStore(tmp_path)
    record = make_record()

    path = store.append("run-20261024", record)
    rows = store.load("run-20261024")

    assert path.name == "run-20261024.jsonl"
    assert rows[0]["record_type"] == "EvidenceRecord"
    assert rows[0]["record_id"] == "E-TECHNICAL-1"
    assert rows[0]["record"]["content_hash"] == record.content_hash


def test_jsonl_store_rejects_unsafe_run_id(tmp_path):
    store = JsonlProvenanceStore(tmp_path)

    try:
        store.path_for("../escape")
    except ValueError as error:
        assert "run_id" in str(error)
    else:
        raise AssertionError("unsafe run_id was accepted")
