from backend.main import SCENARIOS
from engine.calculator import calculate_support
from engine.models import Claim, Fact
from engine.constraint_graph import build_constraint_graph


def make_baseline_facts():
    return [
        Fact(
            "F-001",
            "CERT-01",
            1,
            "quantity_t",
            "Certified quantity: 20.0 t",
            20.0,
            "t",
        ),
        Fact(
            "F-002",
            "MAN-01",
            1,
            "quantity_t",
            "Net transported quantity: 11.2 t",
            11.2,
            "t",
        ),
        Fact(
            "F-003",
            "WB-01",
            1,
            "net_weight_t",
            "Net weight: 18.4 t",
            18.4,
            "t",
        ),
        Fact(
            "F-004",
            "FAC-01",
            1,
            "capacity_t",
            "Declared processing capacity during period: 8.0 t",
            8.0,
            "t",
        ),
    ]


def test_constraint_graph_contains_core_nodes_and_edges():
    artifacts = SCENARIOS["baseline"]

    claim = Claim(
        "CLM-001",
        "e-waste",
        20.0,
        "FAC-001",
        "2026-08-01",
        "2026-08-02",
    )

    facts = make_baseline_facts()

    envelope = calculate_support(
        claim,
        artifacts,
        facts,
    )

    graph = build_constraint_graph(
        claim.__dict__,
        artifacts,
        facts,
        envelope,
    )

    assert graph["claim_id"] == "CLM-001"

    node_ids = {
        node["id"]
        for node in graph["nodes"]
    }

    assert "CLM-001" in node_ids
    assert "CERT-01" in node_ids
    assert "MAN-01" in node_ids
    assert "WB-01" in node_ids
    assert "FAC-01" in node_ids
    assert "CONSTRAINT-BINDING" in node_ids


def test_constraint_graph_detects_receipt_transport_conflict():
    artifacts = SCENARIOS["baseline"]

    claim = Claim(
        "CLM-001",
        "e-waste",
        20.0,
        "FAC-001",
        "2026-08-01",
        "2026-08-02",
    )

    facts = make_baseline_facts()

    envelope = calculate_support(
        claim,
        artifacts,
        facts,
    )

    graph = build_constraint_graph(
        claim.__dict__,
        artifacts,
        facts,
        envelope,
    )

    conflict_edges = [
        edge
        for edge in graph["edges"]
        if edge["edge"] == "CONTRADICTS"
    ]

    assert len(conflict_edges) == 1

    conflict = conflict_edges[0]

    assert conflict["from"] == "WB-01"
    assert conflict["to"] == "MAN-01"
    assert conflict["difference_t"] == 7.2


def test_constraint_graph_keeps_capacity_as_constraint():
    artifacts = SCENARIOS["baseline"]

    claim = Claim(
        "CLM-001",
        "e-waste",
        20.0,
        "FAC-001",
        "2026-08-01",
        "2026-08-02",
    )

    facts = make_baseline_facts()

    envelope = calculate_support(
        claim,
        artifacts,
        facts,
    )

    graph = build_constraint_graph(
        claim.__dict__,
        artifacts,
        facts,
        envelope,
    )

    capacity_edges = [
        edge
        for edge in graph["edges"]
        if edge["edge"] == "SETS_BOUND"
    ]

    assert len(capacity_edges) == 1
    assert capacity_edges[0]["from"] == "FAC-01"

    assert graph["summary"]["final_supportable_t"] == 8.0
    assert graph["summary"]["binding_constraint"] == (
        "processing capacity"
    )