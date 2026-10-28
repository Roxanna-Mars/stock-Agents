"""Offline example: data -> deterministic DCF -> claim -> audit."""

from datetime import date
import json

from src.audit.engine import AuditEngine
from src.compute.operators.dcf import calculate_dcf
from src.domain.models import Claim, DataArtifact
from src.provenance.ledger import ProvenanceLedger


def main() -> None:
    cash_flow_data = DataArtifact.create(
        artifact_id="D-DEMO-FCF-1",
        symbol="sh.600519",
        data_type="cash_flow_forecast",
        provider="demo",
        as_of=date(2026, 10, 24),
        payload={"free_cash_flows": [100.0, 106.0, 112.36, 119.10, 126.25]},
        currency="CNY",
        unit="million",
    )
    valuation = calculate_dcf(
        free_cash_flows=cash_flow_data.payload["free_cash_flows"],
        discount_rate=0.10,
        terminal_growth_rate=0.025,
        shares_outstanding=10.0,
        net_debt=50.0,
        input_refs=[cash_flow_data.artifact_id],
    )
    value_per_share = valuation.result["value_per_share"]
    claim = Claim(
        claim_id="CL-DEMO-VALUE-1",
        text=f"The modeled value is {value_per_share:.2f} CNY per share.",
        claim_type="numeric",
        metric="value_per_share",
        value=value_per_share,
        unit="CNY/share",
        references=[valuation.calculation_id],
    )

    ledger = ProvenanceLedger([cash_flow_data, valuation, claim])
    audit = AuditEngine().audit(ledger)
    print(
        json.dumps(
            {
                "calculation": valuation.model_dump(mode="json"),
                "claim": claim.model_dump(mode="json"),
                "audit": audit.model_dump(mode="json"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
