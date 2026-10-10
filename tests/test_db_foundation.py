from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.schema import Base, Artifact, Company, EvidenceNode, Facility, Case
from db.store import get_or_create_node, link_nodes, upsert_artifact, add_fact


def make_session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def make_case(session, title="Test Case"):
    company = Company(legal_name="Acme Recycling")
    session.add(company)
    session.flush()
    facility = Facility(company_id=company.id, name="Acme Facility", location_text="Delhi")
    session.add(facility)
    session.flush()
    case = Case(company_id=company.id, facility_id=facility.id, title=title)
    session.add(case)
    session.flush()
    return company, facility, case


def test_primary_keys_and_hierarchy():
    session = make_session()
    company, facility, case = make_case(session)
    assert len(company.id) == 36
    assert facility.company_id == company.id
    assert case.company_id == company.id
    assert case.facility_id == facility.id
    assert company.ref.startswith("COM-")
    assert facility.ref.startswith("FAC-")
    assert case.ref.startswith("CAS-")


def test_exact_duplicate_is_not_counted_twice():
    session = make_session()
    _, _, case = make_case(session)
    first, created = upsert_artifact(session, case_id=case.id, filename="invoice.pdf", sha256="a" * 64, artifact_type="invoice", origin_class="claimant_recycler", issuer_name="Acme Recycling", mime_type="application/pdf", storage_path="data/invoice.pdf")
    session.commit()
    second, created_again = upsert_artifact(session, case_id=case.id, filename="invoice-copy.pdf", sha256="a" * 64, artifact_type="invoice", origin_class="claimant_recycler", issuer_name="Acme Recycling", mime_type="application/pdf", storage_path="data/invoice-copy.pdf")
    assert created is True
    assert created_again is False
    assert first.id == second.id


def test_1000_artifacts_share_one_case():
    session = make_session()
    _, _, case = make_case(session)
    for i in range(1000):
        artifact, created = upsert_artifact(session, case_id=case.id, filename=f"document-{i:04d}.pdf", sha256=f"{i:064x}"[-64:], artifact_type="evidence", origin_class="unknown", issuer_name=None, mime_type="application/pdf", storage_path=f"data/documents/{i:04d}.pdf")
        assert created is True
        assert artifact.case_id == case.id
    session.commit()
    count = len(session.query(Artifact).filter(Artifact.case_id == case.id).all())
    assert count == 1000


def test_case_scoped_graph_link_and_fact():
    session = make_session()
    _, _, case = make_case(session)
    artifact, _ = upsert_artifact(session, case_id=case.id, filename="manifest.pdf", sha256="b" * 64, artifact_type="transport_manifest", origin_class="counterparty", issuer_name="MoveFast", mime_type="application/pdf", storage_path="data/manifest.pdf")
    fact = add_fact(session, case_id=case.id, artifact_id=artifact.id, page=1, field="transported_quantity", quote="Net transported quantity: 11.2 t", normalized_value="11.2", unit="t", confidence="high", grounding_state="verified")
    artifact_node = get_or_create_node(session, case_id=case.id, node_type="artifact", entity_id=artifact.id, display_label="Transport Manifest")
    fact_node = get_or_create_node(session, case_id=case.id, node_type="fact", entity_id=fact.id, display_label="Transported quantity = 11.2 t")
    edge = link_nodes(session, case_id=case.id, source_node_id=artifact_node.id, target_node_id=fact_node.id, relationship="ASSERTS", basis="Source-grounded extracted fact")
    assert edge.case_id == case.id


def test_cross_case_link_is_rejected():
    session = make_session()
    _, _, case_a = make_case(session, "Case A")
    _, _, case_b = make_case(session, "Case B")
    node_a = get_or_create_node(session, case_id=case_a.id, node_type="artifact", entity_id="A", display_label="Case A artifact")
    node_b = get_or_create_node(session, case_id=case_b.id, node_type="artifact", entity_id="B", display_label="Case B artifact")
    try:
        link_nodes(session, case_id=case_a.id, source_node_id=node_a.id, target_node_id=node_b.id, relationship="SUPPORTS")
    except ValueError as exc:
        assert "cross case" in str(exc).lower()
    else:
        raise AssertionError("Expected cross-case link to fail.")
