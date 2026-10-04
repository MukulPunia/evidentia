from backend.main import SCENARIOS
from engine.models import Claim
from engine.replay import build_support_replay


def make_claim():
    return Claim(
        "CLM-001",
        "e-waste",
        20.0,
        "FAC-001",
        "2026-08-01",
        "2026-08-02",
    )


def test_replay_contains_all_demo_stages():
    result = build_support_replay(
        SCENARIOS,
        make_claim(),
    )

    assert result["scenarios"] == [
        "baseline",
        "after_manifest",
        "after_shift_record",
    ]

    assert len(result["snapshots"]) == 3


def test_manifest_stage_does_not_change_final_support():
    result = build_support_replay(
        SCENARIOS,
        make_claim(),
    )

    transition = result["transitions"][0]

    assert transition["from"] == "baseline"
    assert transition["to"] == "after_manifest"

    assert transition["final_supportable_before_t"] == 8.0
    assert transition["final_supportable_after_t"] == 8.0
    assert transition["change_t"] == 0.0


def test_shift_stage_raises_support_to_transport_limit():
    result = build_support_replay(
        SCENARIOS,
        make_claim(),
    )

    transition = result["transitions"][1]

    assert transition["from"] == "after_manifest"
    assert transition["to"] == "after_shift_record"

    assert transition["final_supportable_before_t"] == 8.0
    assert transition["final_supportable_after_t"] == 11.2
    assert transition["change_t"] == 3.2

    assert (
        transition["binding_constraint_before"]
        == "processing capacity"
    )

    assert (
        transition["binding_constraint_after"]
        == "transport/custody evidence"
    )

    assert transition["receipt_conflict_after"] is True