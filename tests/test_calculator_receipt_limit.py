from engine.calculator import calculate_support
from engine.models import Artifact, Claim, Fact


def test_lower_receipt_quantity_limits_supported_amount():
    claim = Claim("CLM-TEST", "e-waste", 20.0, "FAC-TEST", "2026-01-01", "2026-01-02")
    artifacts = [
        Artifact("MAN-01", "transport_manifest", "manifest.pdf", "counterparty", "Carrier"),
        Artifact("WB-01", "weighbridge", "receipt.pdf", "independent_system", "Scale"),
    ]
    facts = [
        Fact("F1", "MAN-01", 1, "quantity_t", "Shipped 18 t", 18.0, "t"),
        Fact("F2", "WB-01", 1, "net_weight_t", "Received 10 t", 10.0, "t"),
    ]

    result = calculate_support(claim, artifacts, facts)

    assert result.evidence_supported_t == 10.0
    assert result.final_supportable_t == 10.0
    assert result.binding_constraint == "receipt/custody evidence"
    assert result.receipt_conflict is False


def test_receipt_above_transport_keeps_transport_limit():
    claim = Claim("CLM-TEST", "e-waste", 20.0, "FAC-TEST", "2026-01-01", "2026-01-02")
    artifacts = [
        Artifact("MAN-01", "transport_manifest", "manifest.pdf", "counterparty", "Carrier"),
        Artifact("WB-01", "weighbridge", "receipt.pdf", "independent_system", "Scale"),
    ]
    facts = [
        Fact("F1", "MAN-01", 1, "quantity_t", "Shipped 10 t", 10.0, "t"),
        Fact("F2", "WB-01", 1, "net_weight_t", "Received 18 t", 18.0, "t"),
    ]

    result = calculate_support(claim, artifacts, facts)

    assert result.evidence_supported_t == 10.0
    assert result.receipt_conflict is True
    assert result.custody_gap_t == 8.0


def test_claim_amount_is_not_supported_without_verified_quantity_evidence():
    claim = Claim("CLM-EMPTY", "e-waste", 20.0, "FAC-TEST", "2026-08-01", "2026-08-02")
    result = calculate_support(claim, [], [])

    assert result.claimed_t == 20.0
    assert result.evidence_supported_t == 0.0
    assert result.final_supportable_t == 0.0
    assert result.binding_constraint == "transport/custody evidence"
