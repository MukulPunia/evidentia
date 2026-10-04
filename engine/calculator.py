from __future__ import annotations

from typing import Iterable

from .models import (
    Artifact,
    Claim,
    Fact,
    StageResult,
    SupportEnvelope,
)


def first_value(
    facts: Iterable[Fact],
    artifact_ids: set[str],
    fields: set[str],
):
    for fact in facts:
        if (
            fact.artifact_id in artifact_ids
            and fact.field in fields
            and fact.validation_state == "verified"
        ):
            try:
                return float(fact.normalized_value)
            except (TypeError, ValueError):
                return None

    return None


def calculate_support(
    claim: Claim,
    artifacts: list[Artifact],
    facts: list[Fact],
) -> SupportEnvelope:

    by_type: dict[str, set[str]] = {}

    for artifact in artifacts:
        by_type.setdefault(
            artifact.artifact_type,
            set(),
        ).add(artifact.artifact_id)

    # ---------------------------------------------------------
    # Transport evidence
    # ---------------------------------------------------------

    transport_t = first_value(
        facts,
        by_type.get("transport_manifest", set()),
        {
            "quantity_t",
            "net_weight_t",
        },
    )

    # ---------------------------------------------------------
    # Receipt evidence
    # ---------------------------------------------------------

    receipt_t = first_value(
        facts,
        by_type.get("weighbridge", set()),
        {
            "quantity_t",
            "net_weight_t",
        },
    )

    # ---------------------------------------------------------
    # Processing capacity
    #
    # A validated shift record takes precedence over the
    # baseline facility profile because it is newer,
    # period-specific evidence.
    # ---------------------------------------------------------

    shift_capacity_t = first_value(
        facts,
        by_type.get("shift_record", set()),
        {
            "capacity_t",
        },
    )

    facility_capacity_t = first_value(
        facts,
        by_type.get("facility_profile", set()),
        {
            "capacity_t",
        },
    )

    if shift_capacity_t is not None:
        capacity_t = shift_capacity_t
        capacity_artifact_type = "shift_record"
        capacity_artifact = next(
            (
                artifact
                for artifact in artifacts
                if artifact.artifact_type == "shift_record"
                and artifact.artifact_id
                in by_type.get("shift_record", set())
            ),
            None,
        )

    else:
        capacity_t = facility_capacity_t
        capacity_artifact_type = "facility_profile"
        capacity_artifact = next(
            (
                artifact
                for artifact in artifacts
                if artifact.artifact_type == "facility_profile"
                and artifact.artifact_id
                in by_type.get("facility_profile", set())
            ),
            None,
        )

    # ---------------------------------------------------------
    # Evidence-supported quantity
    # ---------------------------------------------------------

    evidence_supported = claim.quantity_t

    if transport_t is not None:
        evidence_supported = min(
            evidence_supported,
            transport_t,
        )

    if receipt_t is not None:
        evidence_supported = min(
            evidence_supported,
            transport_t
            if transport_t is not None
            else receipt_t,
        )

    # ---------------------------------------------------------
    # Final supportable quantity
    # ---------------------------------------------------------

    final_supportable = evidence_supported
    binding = "none identified"

    if (
        capacity_t is not None
        and capacity_t < final_supportable
    ):
        final_supportable = capacity_t
        binding = "processing capacity"

    elif (
        transport_t is not None
        and transport_t < claim.quantity_t
    ):
        binding = "transport/custody evidence"

    # ---------------------------------------------------------
    # Custody discrepancy
    # ---------------------------------------------------------

    custody_gap = 0.0

    if receipt_t is not None:
        comparison_quantity = (
            transport_t
            if transport_t is not None
            else receipt_t
        )

        custody_gap = max(
            0.0,
            receipt_t - comparison_quantity,
        )

    receipt_conflict = (
        transport_t is not None
        and receipt_t is not None
        and receipt_t > transport_t
    )

    # ---------------------------------------------------------
    # Processing-stage metadata
    # ---------------------------------------------------------

    if capacity_artifact is not None:
        processing_origin = (
            capacity_artifact.origin_class
        )

        if capacity_artifact_type == "shift_record":
            processing_description = (
                "Validated processing shift record"
            )
        else:
            processing_description = (
                "Facility processing capacity reference"
            )

        processing_independent = (
            True
            if capacity_artifact.origin_class
            == "independent_system"
            else None
        )

    else:
        processing_origin = "unknown"
        processing_description = (
            "Processing capacity evidence missing"
        )
        processing_independent = None

    # ---------------------------------------------------------
    # Stage results
    # ---------------------------------------------------------

    stages = [
        StageResult(
            "collection",
            "Claimed collection quantity",
            "claimant_recycler",
            False,
            None,
            "partial",
            "Independent collection evidence not established",
        ),

        StageResult(
            "transport",
            "Linked transport manifest",
            (
                "counterparty"
                if transport_t is not None
                else "unknown"
            ),
            (
                True
                if transport_t is not None
                else None
            ),
            transport_t,
            (
                "supported"
                if transport_t is not None
                else "gap"
            ),
            (
                ""
                if transport_t is not None
                else "Transport evidence missing"
            ),
        ),

        StageResult(
            "receipt",
            "Weighbridge receipt",
            (
                "independent_system"
                if receipt_t is not None
                else "unknown"
            ),
            (
                True
                if receipt_t is not None
                else None
            ),
            receipt_t,
            (
                "conflict"
                if receipt_conflict
                else (
                    "supported"
                    if receipt_t is not None
                    else "gap"
                )
            ),
            (
                f"Receipt exceeds shipped quantity by "
                f"{custody_gap:.1f} t"
                if receipt_conflict
                else (
                    ""
                    if receipt_t is not None
                    else "Receipt evidence missing"
                )
            ),
        ),

        StageResult(
            "processing",
            processing_description,
            processing_origin,
            processing_independent,
            capacity_t,
            (
                "constraint"
                if capacity_t is not None
                else "gap"
            ),
            (
                ""
                if capacity_t is not None
                else "Processing capacity evidence missing"
            ),
        ),

        StageResult(
            "certification",
            "Recycling certificate",
            "claimant_recycler",
            False,
            claim.quantity_t,
            "present",
            (
                "Certificate alone does not independently "
                "corroborate processing"
            ),
        ),
    ]

    assumptions = [
        "Capacity is a constraint, not corroboration.",
        (
            "Unresolved custody discrepancies are not treated "
            "as supported mass."
        ),
        (
            "Only validated facts enter the support calculation."
        ),
        (
            "A validated shift record may update the applicable "
            "processing-capacity constraint."
        ),
    ]

    return SupportEnvelope(
        claimed_t=claim.quantity_t,
        evidence_supported_t=round(
            evidence_supported,
            3,
        ),
        final_supportable_t=round(
            final_supportable,
            3,
        ),
        binding_constraint=binding,
        assumptions=assumptions,
        custody_gap_t=round(
            custody_gap,
            3,
        ),
        receipt_conflict=receipt_conflict,
        stages=stages,
    )