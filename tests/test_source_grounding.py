from backend.main import (
    SCENARIOS,
    attach_local_evidence,
)

from engine.models import Fact

from engine.validator import validate_fact


def test_real_pdf_source_text_is_attached():
    artifacts = attach_local_evidence(
        SCENARIOS["baseline"]
    )

    certificate = next(
        artifact
        for artifact in artifacts
        if artifact.artifact_id == "CERT-01"
    )

    assert certificate.metadata["page_count"] >= 1
    assert certificate.metadata["source_pages"]

    source_text = certificate.text.lower()

    assert "certified quantity" in source_text
    assert "20.0 t" in source_text


def test_fact_quote_is_grounded_in_real_pdf():
    artifacts = attach_local_evidence(
        SCENARIOS["baseline"]
    )

    artifact_map = {
        artifact.artifact_id: artifact
        for artifact in artifacts
    }

    fact = Fact(
        "GROUND-001",
        "MAN-01",
        1,
        "net_transported_quantity",
        "Net transported quantity: 11.2 t",
        11.2,
        "t",
    )

    valid, state = validate_fact(
        fact,
        artifact_map,
    )

    assert valid is True
    assert state == "verified"
    assert fact.field == "quantity_t"


def test_false_quote_is_rejected():
    artifacts = attach_local_evidence(
        SCENARIOS["baseline"]
    )

    artifact_map = {
        artifact.artifact_id: artifact
        for artifact in artifacts
    }

    fact = Fact(
        "GROUND-002",
        "MAN-01",
        1,
        "quantity_t",
        "Net transported quantity: 99.9 t",
        99.9,
        "t",
    )

    valid, state = validate_fact(
        fact,
        artifact_map,
    )

    assert valid is False
    assert state == "quote_not_grounded"