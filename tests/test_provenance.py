from backend.main import SCENARIOS
from engine.provenance import build_provenance_summary


def test_baseline_provenance_groups_correlated_documents():
    artifacts = SCENARIOS["baseline"]

    result = build_provenance_summary(artifacts)

    assert result["document_count"] == 6
    assert result["lineage_group_count"] == 4
    assert result["independence_ratio"] == 0.667

    correlated = result["correlated_documents"]

    assert len(correlated) == 1

    group = correlated[0]

    assert group["root_artifact"] == "DEC-01"
    assert set(group["artifact_ids"]) == {
        "DEC-01",
        "CERT-01",
        "INV-01",
    }
    assert group["document_count"] == 3


def test_derived_from_edges_are_present():
    artifacts = SCENARIOS["baseline"]

    result = build_provenance_summary(artifacts)

    edges = result["edges"]

    assert {
        "from": "CERT-01",
        "edge": "DERIVED_FROM",
        "to": "DEC-01",
    } in edges

    assert {
        "from": "INV-01",
        "edge": "DERIVED_FROM",
        "to": "DEC-01",
    } in edges