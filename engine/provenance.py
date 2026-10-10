
from __future__ import annotations

from collections import defaultdict
from typing import Any

from .models import Artifact


PROVENANCE_EDGES = {
    "DERIVED_FROM",
    "SUPPORTS",
    "CONTRADICTS",
    "MEASURES",
    "HAS_CAPACITY",
    "PRECEDES",
    "REFERENCES",
    "DUPLICATES",
}


def _root_artifact(
    artifact_id: str,
    artifacts: dict[str, Artifact],
) -> str:
    """Follow derived-document links to the original source."""
    visited: set[str] = set()
    current = artifact_id

    while True:
        if current in visited:
            raise ValueError(
                f"Provenance cycle detected at artifact {current}"
            )

        visited.add(current)
        artifact = artifacts.get(current)

        if artifact is None or not artifact.derived_from:
            return current

        if artifact.derived_from not in artifacts:
            return artifact.derived_from

        current = artifact.derived_from


def build_provenance_summary(
    artifacts: list[Artifact],
    extra_edges: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Report document lineage and verified source independence.

    A document's stated origin is not proof that the origin is authentic.
    Derived documents do not count as independent corroboration.
    """
    artifact_map = {
        artifact.artifact_id: artifact
        for artifact in artifacts
    }

    edges: list[dict[str, Any]] = []

    for artifact in artifacts:
        if artifact.derived_from:
            edges.append({
                "from": artifact.artifact_id,
                "edge": "DERIVED_FROM",
                "to": artifact.derived_from,
            })

    if extra_edges:
        for edge in extra_edges:
            if edge.get("edge") in PROVENANCE_EDGES:
                edges.append(edge)

    lineage_groups: dict[str, list[str]] = defaultdict(list)

    for artifact in artifacts:
        root = _root_artifact(artifact.artifact_id, artifact_map)
        lineage_groups[root].append(artifact.artifact_id)

    origin_groups: dict[str, set[str]] = defaultdict(set)

    for artifact in artifacts:
        root = _root_artifact(artifact.artifact_id, artifact_map)
        origin_groups[artifact.origin_class].add(root)

    correlated_documents = []

    for root, members in lineage_groups.items():
        if len(members) > 1:
            correlated_documents.append({
                "root_artifact": root,
                "artifact_ids": members,
                "document_count": len(members),
            })

    # Independence is established only when every document's origin and
    # independence have been explicitly verified, and no document is
    # declared as derived from another.
    independence_established = bool(artifacts) and all(
        artifact.metadata.get("origin_verified") is True
        and artifact.metadata.get("independence_verified") is True
        and not artifact.derived_from
        for artifact in artifacts
    )

    lineage_ratio = (
        round(len(lineage_groups) / len(artifacts), 3)
        if artifacts
        else 0.0
    )

    return {
        "document_count": len(artifacts),
        "lineage_group_count": len(lineage_groups),
        "lineage_group_ratio": lineage_ratio if artifacts else None,
        "lineage_ratio": lineage_ratio,
        "independence_ratio": (
            1.0 if independence_established else None
        ),
        "independence_status": (
            "established"
            if independence_established
            else "not_established"
        ),
        "lineage_groups": [
            {
                "root_artifact": root,
                "artifact_ids": members,
            }
            for root, members in lineage_groups.items()
        ],
        "origin_groups": {
            origin: sorted(roots)
            for origin, roots in origin_groups.items()
        },
        "correlated_documents": correlated_documents,
        "edges": edges,
    }
