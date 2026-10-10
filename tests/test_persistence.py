from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.persistence import persist_analysis
from db.schema import (
    Artifact as DbArtifact,
    Base,
    Case,
    Claim as DbClaim,
    Company,
    EvidenceEdge,
    EvidenceNode,
    Fact as DbFact,
    Facility,
)
from engine.models import Artifact, Fact


def make_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(bind=engine)()


def make_case(session: Session, title: str):
    company = Company(legal_name=f"{title} Company")
    session.add(company)
    session.flush()

    facility = Facility(
        company_id=company.id,
        name=f"{title} Facility",
        location_text="Gurugram, India",
    )
    session.add(facility)
    session.flush()

    case = Case(
        company_id=company.id,
        facility_id=facility.id,
        title=title,
    )
    session.add(case)
    session.flush()

    claim = DbClaim(
        case_id=case.id,
        material="e-waste",
        claimed_quantity="20 t",
        start_date="2026-10-01",
        end_date="2026-10-02",
    )
    session.add(claim)
    session.flush()
    return case, claim


def sample_analysis_records():
    artifacts = [
        Artifact(
            "MAN-01",
            "transport_manifest",
            "manifest.pdf",
            "counterparty",
            "MoveFast Logistics",
            "Net transported quantity: 11.2 t",
            sha256="a" * 64,
            mime_type="application/pdf",
        )
    ]
    facts = [
        Fact(
            "F-01",
            "MAN-01",
            1,
            "quantity_t",
            "Net transported quantity: 11.2 t",
            "11.2",
            "t",
        )
    ]
    graph = {
        "nodes": [
            {"id": "CLAIM", "type": "claim", "label": "Claim"},
            {"id": "MAN-01", "type": "artifact", "label": "Manifest"},
            {"id": "FACT-F-01", "type": "fact", "label": "Quantity = 11.2 t"},
        ],
        "edges": [
            {
                "from": "MAN-01",
                "to": "FACT-F-01",
                "edge": "ASSERTS",
                "reason": "Source-grounded quantity",
            },
            {
                "from": "FACT-F-01",
                "to": "CLAIM",
                "edge": "SUPPORTS",
                "reason": "Fact linked to claim",
            },
        ],
    }
    return artifacts, facts, graph


def test_analysis_persistence_is_idempotent_and_case_scoped():
    session = make_session()
    case_a, claim_a = make_case(session, "Case A")
    case_b, claim_b = make_case(session, "Case B")
    artifacts, facts, graph = sample_analysis_records()

    first = persist_analysis(
        session, case_a, claim_a, artifacts, facts, graph
    )
    second = persist_analysis(
        session, case_a, claim_a, artifacts, facts, graph
    )

    assert first["artifacts_saved"] == 1
    assert first["facts_saved"] == 1
    assert first["graph_nodes_saved"] == 3
    assert first["graph_edges_saved"] == 2
    assert second["artifacts_saved"] == 1
    assert second["facts_saved"] == 1

    # Reuse the same digest and fact content for a different case. The
    # records must be separate even when the file bytes are identical.
    artifacts_b, facts_b, graph_b = sample_analysis_records()
    persist_analysis(
        session, case_b, claim_b, artifacts_b, facts_b, graph_b
    )

    stored_artifacts = session.scalars(
        select(DbArtifact).order_by(DbArtifact.case_id)
    ).all()
    stored_facts = session.scalars(
        select(DbFact).order_by(DbFact.case_id)
    ).all()
    nodes = session.scalars(select(EvidenceNode)).all()
    edges = session.scalars(select(EvidenceEdge)).all()

    assert len(stored_artifacts) == 2
    assert {item.case_id for item in stored_artifacts} == {
        case_a.id,
        case_b.id,
    }
    assert len(stored_facts) == 2
    assert {item.case_id for item in stored_facts} == {
        case_a.id,
        case_b.id,
    }
    assert len(nodes) == 6
    assert len(edges) == 4

    session.close()
