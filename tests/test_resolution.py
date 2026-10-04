from backend.main import SCENARIOS
from engine.calculator import calculate_support
from engine.models import Claim, Fact
from engine.resolution import build_resolution_path


def baseline_envelope():
    artifacts = SCENARIOS["baseline"]

    claim = Claim(
        "CLM-001",
        "e-waste",
        20.0,
        "FAC-001",
        "2026-08-01",
        "2026-08-02",
    )

    facts = [
        Fact(
            "F-001",
            "MAN-01",
            1,
            "quantity_t",
            "Net transported quantity: 11.2 t",
            11.2,
            "t",
        ),
        Fact(
            "F-002",
            "WB-01",
            1,
            "net_weight_t",
            "Net weight: 18.4 t",
            18.4,
            "t",
        ),
        Fact(
            "F-003",
            "FAC-01",
            1,
            "capacity_t",
            "Declared processing capacity during period: 8.0 t",
            8.0,
            "t",
        ),
    ]

    return calculate_support(
        claim,
        artifacts,
        facts,
    )


def test_manifest_does_not_change_current_bottleneck():
    envelope = baseline_envelope()

    result = build_resolution_path(
        "baseline",
        envelope,
    )

    manifest_action = next(
        item
        for item in result["actions"]
        if item["artifact_id"] == "MAN-03"
    )

    assert manifest_action["current_final_t"] == 8.0
    assert manifest_action["potential_final_t"] == 8.0
    assert manifest_action["potential_change_t"] == 0.0


def test_shift_record_can_raise_final_support():
    envelope = baseline_envelope()

    result = build_resolution_path(
        "baseline",
        envelope,
    )

    shift_action = next(
        item
        for item in result["actions"]
        if item["artifact_id"] == "SHIFT-01"
    )

    assert shift_action["current_final_t"] == 8.0
    assert shift_action["potential_final_t"] == 11.2
    assert shift_action["potential_change_t"] == 3.2


def test_receipt_conflict_requires_resolution():
    envelope = baseline_envelope()

    result = build_resolution_path(
        "baseline",
        envelope,
    )

    receipt_action = next(
        item
        for item in result["actions"]
        if item["action_id"] == "RES-003"
    )

    assert receipt_action["stage"] == "receipt"
    assert receipt_action["potential_final_t"] is None
    assert result["full_chain_status"] == "pending_review"