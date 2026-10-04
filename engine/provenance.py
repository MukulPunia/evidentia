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
    """
    Follow DERIVED_FROM relationships back to the original source.

    Example:

        INV-01 -> DEC-01
        CERT-01 -> DEC-01

    Both therefore resolve to DEC-01.
    """

    visited: set[str] = set()
    current = artifact_id

    while True:
        if current in visited:
            raise ValueError(
                f"Provenance cycle detected at artifact {current}"
            )

        visited.add(current)

        artifact = artifacts.get(current)

        if artifact is None:
            return current

        if not artifact.derived_from:
            return current

        if artifact.derived_from not in artifacts:
            return artifact.derived_from

        current = artifact.derived_from


def build_provenance_summary(
    artifacts: list[Artifact],
    extra_edges: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Build a case-scoped provenance summary.

    The purpose is to distinguish:
        - document count
        - source lineage count
        - origin-class diversity
        - correlated documents

    This does NOT decide whether evidence is true.
    It only describes provenance relationships.
    """

    artifact_map = {
        artifact.artifact_id: artifact
        for artifact in artifacts
    }

    edges: list[dict[str, Any]] = []

    for artifact in artifacts:
        if artifact.derived_from:
            edges.append(
                {
                    "from": artifact.artifact_id,
                    "edge": "DERIVED_FROM",
                    "to": artifact.derived_from,
                }
            )

    if extra_edges:
        for edge in extra_edges:
            if edge.get("edge") in PROVENANCE_EDGES:
                edges.append(edge)

    lineage_groups: dict[str, list[str]] = defaultdict(list)

    for artifact in artifacts:
        root = _root_artifact(
            artifact.artifact_id,
            artifact_map,
        )
        lineage_groups[root].append(
            artifact.artifact_id
        )

    origin_groups: dict[str, set[str]] = defaultdict(set)

    for artifact in artifacts:
        root = _root_artifact(
            artifact.artifact_id,
            artifact_map,
        )

        origin_groups[
            artifact.origin_class
        ].add(root)

    correlated_documents = []

    for root, members in lineage_groups.items():
        if len(members) > 1:
            correlated_documents.append(
                {
                    "root_artifact": root,
                    "artifact_ids": members,
                    "document_count": len(members),
                }
            )

    return {
        "document_count": len(artifacts),
        "lineage_group_count": len(lineage_groups),
        "independence_ratio": (
            round(
                len(lineage_groups) / len(artifacts),
                3,
            )
            if artifacts
            else 1.0
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