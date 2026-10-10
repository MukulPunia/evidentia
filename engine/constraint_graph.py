from __future__ import annotations

from typing import Any

from .models import Artifact, Fact, SupportEnvelope


def build_constraint_graph(
    claim: dict[str, Any],
    artifacts: list[Artifact],
    facts: list[Fact],
    envelope: SupportEnvelope,
) -> dict[str, Any]:
    """
    Build a small, case-scoped evidence constraint graph.

    The graph describes relationships between:
    - the claim
    - submitted evidence artifacts
    - facilities
    - quantities
    - constraints

    It does not decide truth or fraud.
    """

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    def add_node(
        node_id: str,
        node_type: str,
        label: str,
        **extra: Any,
    ) -> None:
        nodes.append(
            {
                "id": node_id,
                "type": node_type,
                "label": label,
                **extra,
            }
        )

    def add_edge(
        source: str,
        edge_type: str,
        target: str,
        **extra: Any,
    ) -> None:
        edges.append(
            {
                "from": source,
                "edge": edge_type,
                "to": target,
                **extra,
            }
        )

    # ---------------------------------------------------------
    # Claim node
    # ---------------------------------------------------------

    claim_id = claim["claim_id"]

    add_node(
        claim_id,
        "claim",
        f'{claim["material"]} recycling claim',
        quantity_t=claim["quantity_t"],
        facility_id=claim["facility_id"],
    )

    # ---------------------------------------------------------
    # Artifact nodes
    # ---------------------------------------------------------

    for artifact in artifacts:
        add_node(
            artifact.artifact_id,
            "artifact",
            artifact.filename,
            artifact_type=artifact.artifact_type,
            origin_class=artifact.origin_class,
            issuer=artifact.issuer,
        )

        if artifact.derived_from:
            add_edge(
                artifact.artifact_id,
                "DERIVED_FROM",
                artifact.derived_from,
            )

    # ---------------------------------------------------------
    # Fact nodes + relationships
    # ---------------------------------------------------------

    fact_by_artifact: dict[str, list[Fact]] = {}

    for fact in facts:
        fact_by_artifact.setdefault(
            fact.artifact_id,
            [],
        ).append(fact)

        fact_node_id = f"FACT-{fact.fact_id}"

        add_node(
            fact_node_id,
            "fact",
            fact.field,
            artifact_id=fact.artifact_id,
            value=fact.normalized_value,
            unit=fact.unit,
            confidence=fact.confidence,
        )

        add_edge(
            fact.artifact_id,
            "MEASURES",
            fact_node_id,
        )

    # ---------------------------------------------------------
    # Evidence → claim relationships
    # ---------------------------------------------------------

    supporting_types = {
        "certificate",
        "declaration",
        "invoice",
        "transport_manifest",
        "weighbridge",
    }

    for artifact in artifacts:
        if artifact.artifact_type in supporting_types:
            add_edge(
                artifact.artifact_id,
                "SUPPORTS",
                claim_id,
            )

    # Facility profile is a constraint rather than corroboration.
    for artifact in artifacts:
        if artifact.artifact_type == "facility_profile":
            add_edge(
                artifact.artifact_id,
                "HAS_CAPACITY",
                claim_id,
            )

    # ---------------------------------------------------------
    # Find canonical quantities
    # ---------------------------------------------------------

    quantities: dict[str, float] = {}

    for fact in facts:
        if fact.field in {
            "quantity_t",
            "net_weight_t",
            "capacity_t",
        }:
            try:
                quantities[fact.artifact_id] = float(
                    fact.normalized_value
                )
            except (TypeError, ValueError):
                continue

    # ---------------------------------------------------------
    # Deterministic conflict relationship
    # ---------------------------------------------------------

    transport_artifacts = [
        a
        for a in artifacts
        if a.artifact_type == "transport_manifest"
        and a.artifact_id in quantities
    ]

    receipt_artifacts = [
        a
        for a in artifacts
        if a.artifact_type == "weighbridge"
        and a.artifact_id in quantities
    ]

    if transport_artifacts and receipt_artifacts:
        transport = transport_artifacts[0]
        receipt = receipt_artifacts[0]

        transport_quantity = quantities[transport.artifact_id]
        receipt_quantity = quantities[receipt.artifact_id]

        if receipt_quantity > transport_quantity:
            difference = round(
                receipt_quantity - transport_quantity,
                3,
            )

            add_edge(
                receipt.artifact_id,
                "CONTRADICTS",
                transport.artifact_id,
                reason="receipt exceeds linked transport quantity",
                difference_t=difference,
            )

    # ---------------------------------------------------------
    # Binding constraint
    # ---------------------------------------------------------

    constraint_id = "CONSTRAINT-BINDING"

    add_node(
        constraint_id,
        "constraint",
        envelope.binding_constraint,
        value_t=envelope.final_supportable_t,
    )


    # Link the binding constraint to the evidence that actually sets it.
    binding_label = (envelope.binding_constraint or "").lower()

    if "processing capacity" in binding_label:
        binding_types = {"facility_profile", "shift_record"}
    elif "transport" in binding_label:
        binding_types = {"transport_manifest"}
    elif "receipt" in binding_label or "custody" in binding_label:
        binding_types = {"weighbridge"}
    else:
        binding_types = set()

    binding_candidates = [
        artifact
        for artifact in artifacts
        if artifact.artifact_type in binding_types
        and artifact.artifact_id in quantities
        and not artifact.derived_from
    ]

    # Prefer the source whose quantity matches the final support limit.
    target_quantity = float(envelope.final_supportable_t)

    matching_candidates = [
        artifact
        for artifact in binding_candidates
        if abs(
            quantities[artifact.artifact_id] - target_quantity
        ) < 0.001
    ]

    if not matching_candidates and binding_candidates:
        lowest_quantity = min(
            quantities[artifact.artifact_id]
            for artifact in binding_candidates
        )

        matching_candidates = [
            artifact
            for artifact in binding_candidates
            if abs(
                quantities[artifact.artifact_id] - lowest_quantity
            ) < 0.001
        ]

    for artifact in matching_candidates:
        add_edge(
            artifact.artifact_id,
            "SETS_BOUND",
            constraint_id,
        )


    # ---------------------------------------------------------
    # Summary
    # ---------------------------------------------------------

    return {
        "claim_id": claim_id,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": edges,
        "summary": {
            "claimed_t": envelope.claimed_t,
            "evidence_supported_t": envelope.evidence_supported_t,
            "final_supportable_t": envelope.final_supportable_t,
            "binding_constraint": envelope.binding_constraint,
            "receipt_conflict": envelope.receipt_conflict,
            "custody_gap_t": envelope.custody_gap_t,
        },
    }