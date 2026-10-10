"""Case-scoped persistence for analyzed recycling evidence."""

from __future__ import annotations

import hashlib
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.schema import (
    Artifact as DbArtifact,
    Case as DbCase,
    Claim as DbClaim,
    Fact as DbFact,
)
from db.store import add_fact, get_or_create_node, link_nodes, upsert_artifact
from engine.models import Artifact, Fact


def persist_analysis(
    session: Session,
    case_record: DbCase,
    claim_record: DbClaim,
    artifacts: list[Artifact],
    facts: list[Fact],
    constraint_graph: dict,
) -> dict[str, int]:
    """
    Save documents, facts, and evidence graph links to the selected case.

    Reuse stable database IDs for duplicate files, save explicit
    parent-document links, and keep all records within the selected case.
    """
    stored_artifacts: dict[str, DbArtifact] = {}
    created_by_artifact: dict[str, bool] = {}

    # ---------------------------------------------------------
    # 1. Save or reuse each document using its SHA-256 hash.
    # ---------------------------------------------------------
    for artifact in artifacts:
        digest = artifact.sha256

        if (
            not digest
            and artifact.local_path
            and Path(artifact.local_path).is_file()
        ):
            digest = hashlib.sha256(
                Path(artifact.local_path).read_bytes()
            ).hexdigest()

        if not digest:
            raise ValueError(
                f"Cannot persist {artifact.filename}: missing file hash."
            )

        stored, created = upsert_artifact(
            session,
            case_id=case_record.id,
            filename=artifact.filename,
            sha256=digest,
            artifact_type=artifact.artifact_type,
            origin_class=artifact.origin_class or "unknown",
            issuer_name=(
                artifact.issuer
                if artifact.issuer and artifact.issuer != "Unknown"
                else None
            ),
            mime_type=artifact.mime_type or "application/pdf",
            storage_path=artifact.local_path,
        )

        # Refresh known source information without overwriting it with
        # unknown values on a subsequent analysis.
        if not created:
            if artifact.origin_class and artifact.origin_class != "unknown":
                stored.origin_class = artifact.origin_class

            if artifact.issuer and artifact.issuer != "Unknown":
                stored.issuer_name = artifact.issuer

            if artifact.artifact_type and not stored.artifact_type:
                stored.artifact_type = artifact.artifact_type

        stored_artifacts[artifact.artifact_id] = stored
        created_by_artifact[artifact.artifact_id] = created

    # Ensure all document records exist before linking their parents.
    session.flush()

    # ---------------------------------------------------------
    # 2. Save parent-document relationships using database IDs.
    # ---------------------------------------------------------
    linked_relationship_pairs: set[tuple[str, str]] = set()

    for artifact in artifacts:
        child = stored_artifacts.get(artifact.artifact_id)

        if child is None:
            continue

        artifact.metadata["database_artifact_id"] = child.id
        artifact.metadata["database_artifact_ref"] = child.ref
        artifact.metadata["database_deduplicated"] = (
            not created_by_artifact.get(artifact.artifact_id, False)
        )

        parent_temp_id = artifact.derived_from

        if not parent_temp_id:
            artifact.metadata.setdefault(
                "database_provenance_status",
                "no_parent_link",
            )
            continue

        parent = stored_artifacts.get(parent_temp_id)

        if parent is None:
            artifact.metadata["database_provenance_status"] = (
                "parent_not_found_in_batch"
            )
            continue

        if parent.id == child.id:
            artifact.metadata["database_provenance_status"] = (
                "self_link_rejected"
            )
            continue

        if (
            parent.case_id != case_record.id
            or child.case_id != case_record.id
        ):
            raise ValueError(
                "Document relationships cannot cross case boundaries."
            )

        existing_parent_id = child.derived_from_artifact_id

        if existing_parent_id not in (None, parent.id):
            artifact.metadata["database_provenance_status"] = (
                "existing_parent_conflict"
            )
            continue

        if existing_parent_id is None:
            child.derived_from_artifact_id = parent.id

        linked_relationship_pairs.add((child.id, parent.id))

        artifact.metadata["database_parent_artifact_id"] = parent.id
        artifact.metadata["database_provenance_status"] = "linked"

    session.flush()

    # ---------------------------------------------------------
    # 3. Save or reuse validated facts.
    # ---------------------------------------------------------
    def canonical_value(value):
        if value is None or not str(value).strip():
            return None

        text = str(value).strip()

        try:
            number = Decimal(text)
            if number.is_finite():
                return ("number", format(number.normalize(), "f"))
        except (InvalidOperation, ValueError):
            pass

        return ("text", " ".join(text.casefold().split()))

    def canonical_unit(value):
        unit = " ".join((value or "").casefold().split())

        unit_aliases = {
            "tonne": "t",
            "tonnes": "t",
            "ton": "t",
            "tons": "t",
        }

        return unit_aliases.get(unit, unit)

    def canonical_quote(value):
        return " ".join(
            re.findall(r"\w+", (value or "").casefold())
        )

    stored_facts: dict[str, DbFact] = {}

    for fact in facts:
        stored_artifact = stored_artifacts.get(fact.artifact_id)

        if stored_artifact is None:
            continue

        incoming_value = canonical_value(fact.normalized_value)
        incoming_unit = canonical_unit(fact.unit)
        incoming_quote = canonical_quote(fact.quote)

        # Search by stable fact location and field first.
        candidates = session.execute(
            select(DbFact)
            .where(
                DbFact.case_id == case_record.id,
                DbFact.artifact_id == stored_artifact.id,
                DbFact.page == fact.page,
                DbFact.field == fact.field,
            )
            .order_by(DbFact.id)
        ).scalars().all()

        existing_fact = None

        for candidate in candidates:
            candidate_value = canonical_value(
                candidate.normalized_value
            )
            candidate_unit = canonical_unit(candidate.unit)

            if (
                incoming_value is not None
                and candidate_value == incoming_value
                and candidate_unit == incoming_unit
            ):
                # Numeric/text values match even if Gemini changes
                # capitalization, punctuation, or quote wording.
                existing_fact = candidate
                break

            if (
                incoming_value is None
                and candidate_value is None
                and candidate_unit == incoming_unit
                and canonical_quote(candidate.quote) == incoming_quote
            ):
                # When there is no normalized value, use a normalized
                # quote so different punctuation/capitalization does
                # not create another copy.
                existing_fact = candidate
                break

        if existing_fact is None:
            existing_fact = add_fact(
                session,
                case_id=case_record.id,
                artifact_id=stored_artifact.id,
                page=fact.page,
                field=fact.field,
                quote=fact.quote,
                normalized_value=(
                    str(fact.normalized_value)
                    if fact.normalized_value is not None
                    else None
                ),
                unit=fact.unit,
                confidence=fact.confidence,
                grounding_state="verified",
            )

        stored_facts[fact.fact_id] = existing_fact

    session.flush()


    # ---------------------------------------------------------
    # 4. Create or reuse case-scoped graph nodes.
    # ---------------------------------------------------------
    graph_nodes: dict[str, str] = {}

    for item in constraint_graph.get("nodes", []):
        logical_id = str(item.get("id", ""))
        node_type = str(item.get("type", "evidence"))

        if not logical_id:
            continue

        if node_type == "claim":
            entity_id = claim_record.id

        elif node_type == "artifact" and logical_id in stored_artifacts:
            entity_id = stored_artifacts[logical_id].id

        elif node_type == "fact" and logical_id.startswith("FACT-"):
            fact_key = logical_id.removeprefix("FACT-")
            fact_record = stored_facts.get(fact_key)

            if fact_record is not None:
                entity_id = fact_record.id
            else:
                entity_id = str(
                    uuid5(
                        NAMESPACE_URL,
                        f"{case_record.id}:{node_type}:{logical_id}",
                    )
                )

        else:
            entity_id = str(
                uuid5(
                    NAMESPACE_URL,
                    f"{case_record.id}:{node_type}:{logical_id}",
                )
            )

        node = get_or_create_node(
            session,
            case_id=case_record.id,
            node_type=node_type,
            entity_id=entity_id,
            display_label=str(
                item.get("label") or logical_id or "Evidence item"
            )[:255],
        )

        graph_nodes[logical_id] = node.id

    session.flush()

    # ---------------------------------------------------------
    # 5. Save valid graph edges.
    # ---------------------------------------------------------
    saved_edge_signatures: set[tuple[str, str, str]] = set()

    for edge in constraint_graph.get("edges", []):
        source_id = graph_nodes.get(str(edge.get("from", "")))
        target_id = graph_nodes.get(str(edge.get("to", "")))
        relationship = str(edge.get("edge", "")).strip()

        if not source_id or not target_id or not relationship:
            continue

        if source_id == target_id:
            continue

        signature = (source_id, target_id, relationship)

        if signature in saved_edge_signatures:
            continue

        link_nodes(
            session,
            case_id=case_record.id,
            source_node_id=source_id,
            target_node_id=target_id,
            relationship=relationship,
            basis=str(
                edge.get("reason")
                or edge.get("basis")
                or relationship.replace("_", " ").lower()
            ),
            confidence=(
                str(edge["confidence"])
                if edge.get("confidence") is not None
                else None
            ),
        )

        saved_edge_signatures.add(signature)

    # ---------------------------------------------------------
    # 6. Commit all persistence changes and return statistics.
    # ---------------------------------------------------------
    session.commit()

    unique_artifact_ids = {
        record.id for record in stored_artifacts.values()
    }

    unique_fact_ids = {
        record.id for record in stored_facts.values()
    }

    unique_graph_node_ids = set(graph_nodes.values())

    return {
        "artifacts_saved": len(unique_artifact_ids),
        "facts_saved": len(unique_fact_ids),
        "graph_nodes_saved": len(unique_graph_node_ids),
        "graph_edges_saved": len(saved_edge_signatures),
        "derived_relationships_saved": len(linked_relationship_pairs),
        "duplicate_artifact_references_reused": (
            len(stored_artifacts) - len(unique_artifact_ids)
        ),
    }
