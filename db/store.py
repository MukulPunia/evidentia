from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .schema import Artifact, EvidenceEdge, EvidenceNode, Fact


def get_or_create_node(session: Session, *, case_id: str, node_type: str, entity_id: str, display_label: str) -> EvidenceNode:
    stmt = select(EvidenceNode).where(
        EvidenceNode.case_id == case_id,
        EvidenceNode.node_type == node_type,
        EvidenceNode.entity_id == entity_id,
    )
    node = session.scalar(stmt)
    if node:
        return node
    node = EvidenceNode(case_id=case_id, node_type=node_type, entity_id=entity_id, display_label=display_label)
    session.add(node)
    session.flush()
    return node


def link_nodes(session: Session, *, case_id: str, source_node_id: str, target_node_id: str, relationship: str, basis: str | None = None, confidence: str | None = None) -> EvidenceEdge:
    source = session.get(EvidenceNode, source_node_id)
    target = session.get(EvidenceNode, target_node_id)
    if not source or not target:
        raise ValueError("Both evidence nodes must exist.")
    if source.case_id != case_id or target.case_id != case_id:
        raise ValueError("Evidence link cannot cross case boundaries.")
    stmt = select(EvidenceEdge).where(
        EvidenceEdge.case_id == case_id,
        EvidenceEdge.source_node_id == source_node_id,
        EvidenceEdge.target_node_id == target_node_id,
        EvidenceEdge.relationship == relationship,
    )
    existing = session.scalar(stmt)
    if existing:
        return existing
    edge = EvidenceEdge(case_id=case_id, source_node_id=source_node_id, target_node_id=target_node_id, relationship=relationship, basis=basis, confidence=confidence)
    session.add(edge)
    session.flush()
    return edge


def upsert_artifact(session: Session, *, case_id: str, filename: str, sha256: str, artifact_type: str | None, origin_class: str, issuer_name: str | None, mime_type: str | None, storage_path: str | None, derived_from_artifact_id: str | None = None) -> tuple[Artifact, bool]:
    stmt = select(Artifact).where(Artifact.case_id == case_id, Artifact.sha256 == sha256)
    existing = session.scalar(stmt)
    if existing:
        return existing, False
    artifact = Artifact(case_id=case_id, filename=filename, sha256=sha256, artifact_type=artifact_type, origin_class=origin_class, issuer_name=issuer_name, mime_type=mime_type, storage_path=storage_path, derived_from_artifact_id=derived_from_artifact_id)
    session.add(artifact)
    session.flush()
    return artifact, True


def add_fact(session: Session, *, case_id: str, artifact_id: str, page: int, field: str, quote: str, normalized_value: str | None, unit: str | None, confidence: str | None, grounding_state: str) -> Fact:
    artifact = session.get(Artifact, artifact_id)
    if not artifact:
        raise ValueError("Artifact does not exist.")
    if artifact.case_id != case_id:
        raise ValueError("Fact cannot reference an artifact from another case.")
    fact = Fact(case_id=case_id, artifact_id=artifact_id, page=page, field=field, quote=quote, normalized_value=normalized_value, unit=unit, confidence=confidence, grounding_state=grounding_state)
    session.add(fact)
    session.flush()
    return fact
