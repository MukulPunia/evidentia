from __future__ import annotations

from typing import Any

from .models import Artifact, Fact


FIELD_ALIASES = {
    "quantity": "quantity_t",
    "quantity_t": "quantity_t",
    "certified_quantity": "quantity_t",
    "certificate_quantity": "quantity_t",
    "invoice_quantity": "quantity_t",
    "declared_quantity": "quantity_t",
    "recycling_quantity": "quantity_t",
    "net_transported_quantity": "quantity_t",
    "transported_quantity": "quantity_t",
    "transport_quantity": "quantity_t",
    "shipped_quantity": "quantity_t",
    "net_weight": "net_weight_t",
    "net_weight_t": "net_weight_t",
    "received_quantity": "net_weight_t",
    "receipt_quantity": "net_weight_t",
    "capacity": "capacity_t",
    "capacity_t": "capacity_t",
    "processing_capacity": "capacity_t",
    "facility_capacity": "capacity_t",
    "declared_capacity": "capacity_t",
    "declared_processing_capacity": "capacity_t",
    "validated_processing_capacity": "capacity_t",
    "maximum_processing_capacity": "capacity_t",
}


def normalize_fact_field(
    field: str,
) -> str:
    """
    Convert Gemini field names to the canonical engine schema.
    """

    normalized = (
        field
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )

    return FIELD_ALIASES.get(
        normalized,
        normalized,
    )


def normalize_source_text(
    value: str,
) -> str:
    """
    Normalize source and quote text so harmless differences in
    spacing, punctuation, and capitalization do not break grounding.
    """

    characters = []

    for char in (value or "").lower():
        if char.isalnum():
            characters.append(char)
        else:
            characters.append(" ")

    return " ".join(
        "".join(characters).split()
    )


def quote_is_grounded(
    fact: Fact,
    artifact: Artifact,
) -> bool:
    """
    Check whether Gemini's quote appears in the actual source page.
    """

    source_pages = artifact.metadata.get(
        "source_pages",
        [],
    )

    if not source_pages:
        return False

    if fact.page < 1 or fact.page > len(source_pages):
        return False

    page_text = source_pages[
        fact.page - 1
    ].get("text", "")

    source_normalized = normalize_source_text(
        page_text
    )

    quote_normalized = normalize_source_text(
        fact.quote
    )

    if not quote_normalized:
        return False

    return (
        quote_normalized
        in source_normalized
    )


def validate_fact(
    fact: Fact,
    artifacts: dict[str, Artifact],
) -> tuple[bool, str]:
    """
    Validate and canonicalize one Gemini-extracted fact.

    A fact can only become verified when its source quote is actually
    grounded in the corresponding PDF page.
    """

    artifact = artifacts.get(
        fact.artifact_id
    )

    if artifact is None:
        fact.validation_state = "rejected"
        return False, "artifact_not_found"

    fact.field = normalize_fact_field(
        fact.field
    )

    if fact.page < 1:
        fact.validation_state = "rejected"
        return False, "invalid_page"

    page_count = artifact.metadata.get(
        "page_count"
    )

    if (
        page_count is not None
        and fact.page > page_count
    ):
        fact.validation_state = "rejected"
        return False, "page_not_found"

    # Actual PDF source grounding.
    if not quote_is_grounded(
        fact,
        artifact,
    ):
        fact.validation_state = "rejected"
        return False, "quote_not_grounded"

    numeric_fields = {
        "quantity_t",
        "net_weight_t",
        "capacity_t",
    }

    if fact.field in numeric_fields:

        if fact.normalized_value is None:
            fact.validation_state = "rejected"
            return False, "missing_numeric_value"

        try:
            fact.normalized_value = float(
                fact.normalized_value
            )
        except (
            TypeError,
            ValueError,
        ):
            fact.validation_state = "rejected"
            return False, "invalid_numeric_value"

    if fact.unit:
        fact.unit = fact.unit.strip().lower()

        allowed_units = {
            "t",
            "kg",
            "tonne",
            "tonnes",
        }

        if fact.unit not in allowed_units:
            fact.validation_state = "rejected"
            return False, "unsupported_unit"

    fact.validation_state = "verified"

    return True, "verified"


def validate_extraction_coverage(
    artifacts: list[Artifact],
    raw_facts: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Check whether every submitted artifact produced at least one
    extracted fact.
    """

    artifact_ids = {
        artifact.artifact_id
        for artifact in artifacts
    }

    extracted_artifact_ids = {
        str(fact.get("artifact_id"))
        for fact in raw_facts
        if fact.get("artifact_id")
    }

    covered_ids = (
        artifact_ids
        & extracted_artifact_ids
    )

    rows = []

    for artifact in artifacts:
        if artifact.artifact_id in covered_ids:
            rows.append(
                {
                    "artifact_id": artifact.artifact_id,
                    "filename": artifact.filename,
                    "status": "covered",
                }
            )
        else:
            rows.append(
                {
                    "artifact_id": artifact.artifact_id,
                    "filename": artifact.filename,
                    "status": "no_fact_extracted",
                }
            )

    expected = len(artifact_ids)
    covered = len(covered_ids)

    coverage_pct = (
        round(
            (covered / expected) * 100,
            1,
        )
        if expected
        else 100.0
    )

    return {
        "expected_artifacts": expected,
        "artifacts_with_facts": covered,
        "coverage_pct": coverage_pct,
        "complete": covered == expected,
        "artifacts": rows,
    }