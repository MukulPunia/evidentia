from __future__ import annotations

import re

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


def _first_numeric_fact(
    facts: Iterable[Fact],
    artifact_ids: set[str],
    fields: set[str],
) -> Fact | None:
    """Return the first verified numeric fact matching the requested fields."""
    for fact in facts:
        if (
            fact.artifact_id not in artifact_ids
            or fact.field not in fields
            or fact.validation_state != "verified"
            or fact.normalized_value is None
        ):
            continue

        try:
            float(fact.normalized_value)
            return fact
        except (TypeError, ValueError):
            continue

    return None


def _artifact_facility_id(artifact: Artifact | None) -> str | None:
    """Extract a facility ID from a document's text, when available."""
    if artifact is None:
        return None

    match = re.search(
        r"\bFacility(?:\s+ID)?\s*[:=]?\s+(FAC[-_ ]?[A-Z0-9]+)\b",
        artifact.text or "",
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    return re.sub(r"[\s_]+", "-", match.group(1).upper())


def _independence_value(
    artifact: Artifact | None,
) -> bool | None:
    """
    Return True only for explicitly verified independence.
    Known claimant-side evidence is not independent corroboration.
    """
    if artifact is None:
        return None

    if artifact.origin_class == "claimant_recycler":
        return False

    if (
        artifact.metadata.get("origin_verified") is True
        and artifact.metadata.get("independence_verified") is True
    ):
        return True

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

        # Exclude facts belonging to documents that failed period validation.
    # Artifacts without a period check remain available to legacy callers;
    # the production analysis routes will require a period check.
    period_excluded_ids = {
        artifact.artifact_id
        for artifact in artifacts
        if isinstance(
            artifact.metadata.get("period_check"),
            dict,
        )
        and artifact.metadata["period_check"].get(
            "eligible_for_calculation"
        ) is not True
    }

    calculation_facts = [
        fact
        for fact in facts
        if fact.artifact_id not in period_excluded_ids
    ]

    # ---------------------------------------------------------
    # Transport evidence
    # ---------------------------------------------------------

    transport_fact = _first_numeric_fact(
        calculation_facts,
        by_type.get("transport_manifest", set()),
        {"quantity_t", "net_weight_t"},
    )

    transport_t = (
        float(transport_fact.normalized_value)
        if transport_fact is not None
        else None
    )
    # ---------------------------------------------------------
    # Receipt evidence
    # ---------------------------------------------------------

    receipt_fact = _first_numeric_fact(
        calculation_facts,
        by_type.get("weighbridge", set()),
        {"quantity_t", "net_weight_t"},
    )

    receipt_t = (
        float(receipt_fact.normalized_value)
        if receipt_fact is not None
        else None
    )

    # ---------------------------------------------------------
    # Processing capacity
    #
    # A validated shift record takes precedence over the
    # baseline facility profile because it is newer,
    # period-specific evidence.
    # ---------------------------------------------------------


    # ---------------------------------------------------------
    # Processing capacity
    # ---------------------------------------------------------

    shift_fact = _first_numeric_fact(
        calculation_facts,
        by_type.get("shift_record", set()),
        {"capacity_t"},
    )

    facility_fact = _first_numeric_fact(
        calculation_facts,
        by_type.get("facility_profile", set()),
        {"capacity_t"},
    )

    shift_capacity_t = (
        float(shift_fact.normalized_value)
        if shift_fact is not None
        else None
    )

    facility_capacity_t = (
        float(facility_fact.normalized_value)
        if facility_fact is not None
        else None
    )

    artifact_by_id = {
        artifact.artifact_id: artifact
        for artifact in artifacts
    }

    shift_artifact = (
        artifact_by_id.get(shift_fact.artifact_id)
        if shift_fact is not None
        else None
    )

    facility_artifact = (
        artifact_by_id.get(facility_fact.artifact_id)
        if facility_fact is not None
        else None
    )

    shift_period = (
        shift_artifact.metadata.get("period_check")
        if shift_artifact is not None
        else None
    )

    shift_period_valid = (
        not isinstance(shift_period, dict)
        or shift_period.get("eligible_for_calculation") is True
    )

    # A shift can replace the facility profile only after its origin and
    # independence are verified and its facility linkage is established.
    shift_source_verified = (
        shift_artifact is not None
        and shift_artifact.metadata.get("origin_verified") is True
        and shift_artifact.metadata.get("independence_verified") is True
        and shift_period_valid
    )

    facility_linked = False

    if (
        shift_artifact is not None
        and shift_artifact.metadata.get("facility_link_verified") is True
    ):
        facility_linked = True
    elif shift_artifact is not None and facility_artifact is not None:
        shift_facility_id = _artifact_facility_id(shift_artifact)
        profile_facility_id = _artifact_facility_id(facility_artifact)

        facility_linked = (
            shift_facility_id is not None
            and profile_facility_id is not None
            and shift_facility_id == profile_facility_id
        )

    use_shift_capacity = (
        shift_capacity_t is not None
        and shift_source_verified
        and facility_linked
    )

    if use_shift_capacity:
        capacity_t = shift_capacity_t
        capacity_artifact_type = "shift_record"
        capacity_artifact = shift_artifact
    else:
        capacity_t = facility_capacity_t
        capacity_artifact_type = (
            "facility_profile"
            if facility_capacity_t is not None
            else None
        )
        capacity_artifact = facility_artifact

    # ---------------------------------------------------------
    # Evidence-supported quantity
    # ---------------------------------------------------------

    # A claim is an assertion, not corroborating evidence. Begin at zero and
    # only establish a quantity when a verified transport or receipt fact is
    # available. This prevents missing / out-of-period facts from silently
    # turning the claimed amount into a fully supported amount.
    if transport_t is not None:
        evidence_supported = min(claim.quantity_t, transport_t)
    elif receipt_t is not None:
        evidence_supported = min(claim.quantity_t, receipt_t)
    else:
        evidence_supported = 0.0

    # A lower receipt quantity is a hard evidence limit. If the receipt is
    # higher than transport, keep the transported quantity and report the
    # custody discrepancy separately.
    if receipt_t is not None and evidence_supported > 0:
        evidence_supported = min(evidence_supported, receipt_t)

    # ---------------------------------------------------------
    # Final supportable quantity
    # ---------------------------------------------------------

    final_supportable = evidence_supported
    if transport_t is None:
        binding = "transport/custody evidence"
    elif receipt_t is None:
        binding = "receipt/custody evidence"
    elif capacity_t is None:
        binding = "processing capacity"
    else:
        binding = "none identified"

    if (
        capacity_t is not None
        and capacity_t < final_supportable
    ):
        final_supportable = capacity_t
        binding = "processing capacity"

    elif (
        receipt_t is not None
        and receipt_t < claim.quantity_t
        and (transport_t is None or receipt_t <= transport_t)
    ):
        binding = "receipt/custody evidence"

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
        processing_origin = capacity_artifact.origin_class

        if capacity_artifact_type == "shift_record":
            processing_description = "Validated processing shift record"
        else:
            processing_description = "Facility processing capacity reference"

        processing_independent = _independence_value(capacity_artifact)

    else:
        processing_origin = "unknown"
        processing_description = "Processing capacity evidence missing"
        processing_independent = None

    transport_artifact = (
        artifact_by_id.get(
            transport_fact.artifact_id
        )
        if transport_fact is not None
        else None
    )

    receipt_artifact = (
        artifact_by_id.get(
            receipt_fact.artifact_id
        )
        if receipt_fact is not None
        else None
    )


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
                transport_artifact.origin_class
                if transport_artifact is not None
                else "unknown"
            ),
            _independence_value(transport_artifact),
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
                receipt_artifact.origin_class
                if receipt_artifact is not None
                else "unknown"
            ),
            _independence_value(receipt_artifact),
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