from engine.intake_gate import (
    assess_document_relevance,
)
from engine.models import Artifact


CLAIM = {
    "claim_id": "CLM-001",
    "material": "e-waste",
    "quantity_t": 20.0,
    "facility_id": "FAC-001",
}


def test_recycling_certificate_is_accepted():
    artifact = Artifact(
        "A-001",
        "certificate",
        "recycling_certificate.pdf",
        "unknown",
        "Unknown",
        "Recycling certificate for e-waste. Certified quantity: 20.0 t",
    )

    result = assess_document_relevance(
        artifact,
        CLAIM,
    )

    assert result["status"] == "accepted"
    assert result["confidence"] == "high"
    assert result["stamp_required"] is False


def test_transport_manifest_is_accepted():
    artifact = Artifact(
        "A-002",
        "transport_manifest",
        "transport_manifest.pdf",
        "unknown",
        "Unknown",
        "Transport manifest. Net transported quantity: 11.2 t",
    )

    result = assess_document_relevance(
        artifact,
        CLAIM,
    )

    assert result["status"] == "accepted"


def test_school_marksheet_is_excluded():
    artifact = Artifact(
        "A-003",
        "unknown",
        "school_marksheet.pdf",
        "unknown",
        "Unknown",
        (
            "Student academic record. "
            "Semester examination grades and subjects."
        ),
    )

    result = assess_document_relevance(
        artifact,
        CLAIM,
    )

    assert result["status"] == "excluded"
    assert result["confidence"] == "high"


def test_unknown_document_goes_to_review():
    artifact = Artifact(
        "A-004",
        "unknown",
        "document.pdf",
        "unknown",
        "Unknown",
        "General administrative document.",
    )

    result = assess_document_relevance(
        artifact,
        CLAIM,
    )

    assert result["status"] == "review"


def test_stamp_is_not_required():
    artifact = Artifact(
        "A-005",
        "facility_profile",
        "facility_profile.pdf",
        "unknown",
        "Unknown",
        (
            "Facility profile. "
            "Declared processing capacity during period: 8.0 t."
        ),
    )

    result = assess_document_relevance(
        artifact,
        CLAIM,
    )

    assert result["status"] == "accepted"
    assert result["stamp_required"] is False


def test_relevant_document_without_known_type_can_be_accepted():
    artifact = Artifact(
        "A-006",
        "unknown",
        "processing_record.pdf",
        "unknown",
        "Unknown",
        (
            "Recycling facility processing record "
            "for e-waste material, 16.0 t processing capacity."
        ),
    )

    result = assess_document_relevance(
        artifact,
        CLAIM,
    )

    assert result["status"] == "accepted"

def test_paper_card_contract_is_excluded_from_ewaste_claim():
    artifact = Artifact(
        "A-PAPER",
        "unknown",
        "27176-Paper-cardboard-recycling.pdf",
        "unknown",
        "Unknown",
        (
            "Suffolk paper and cardboard recycling contract. "
            "Historical total 53,600 tonnes. The facility processes paper, card, "
            "plastic and metal; annual recovery rate was reported for 2017/18."
        ),
    )

    result = assess_document_relevance(artifact, CLAIM)

    assert result["status"] == "excluded"
    assert result["material_match"] is False
    assert "material" in result["reason"].lower()
    assert "claim_material_mismatch" in result["signals"]


def test_matching_paper_card_claim_is_not_excluded_by_material_scope():
    artifact = Artifact(
        "A-PAPER-MATCH",
        "unknown",
        "paper_card_receiving_record.pdf",
        "unknown",
        "Unknown",
        "Paper and cardboard recycling receiving record, net weight: 10 tonnes.",
    )
    claim = {**CLAIM, "material": "paper/cardboard"}
    result = assess_document_relevance(artifact, claim)

    assert result["status"] != "excluded"
    assert result["material_match"] is True
