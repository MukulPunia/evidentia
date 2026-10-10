
from __future__ import annotations

from copy import deepcopy
from typing import Any

from .calculator import calculate_support
from .models import Artifact, Claim, Fact
from .provenance import build_provenance_summary
from .constraint_graph import build_constraint_graph
from .resolution import build_resolution_path
from .validator import validate_fact, assess_artifact_periods
from gemini.service import demo_extraction


def analyze_scenario_deterministically(
    scenario_name: str,
    scenarios: dict[str, list[Artifact]],
    claim: Claim,
) -> dict[str, Any]:
    """Analyze a predefined scenario without making Gemini requests."""

    # Never mutate the shared scenario fixtures.
    artifacts = deepcopy(scenarios[scenario_name])

    for artifact in artifacts:
        artifact.metadata = dict(artifact.metadata or {})
        artifact.metadata.pop("period_check", None)

        source_text = artifact.text or ""

        # The predefined demo fixtures stand for evidence in this
        # claim period. Preserve any explicit dates already present.
        if not any(
            date in source_text
            for date in ("2026-08-01", "2026-08-02")
        ):
            source_text += (
                f"\nEvidence period: "
                f"{claim.period_start} to {claim.period_end}"
            )

        artifact.text = source_text
        artifact.metadata["source_pages"] = [
            {"page": 1, "text": source_text}
        ]
        artifact.metadata["page_count"] = 1

    assess_artifact_periods(claim, artifacts)

    artifact_dicts = [
        artifact.__dict__
        for artifact in artifacts
    ]

    raw_facts = demo_extraction(artifact_dicts)

    artifact_map = {
        artifact.artifact_id: artifact
        for artifact in artifacts
    }

    facts: list[Fact] = []

    for index, raw in enumerate(raw_facts, 1):
        fact = Fact(
            f"REPLAY-{index:03d}",
            raw["artifact_id"],
            int(raw.get("page", 1)),
            raw["field"],
            raw["quote"],
            raw.get("normalized_value"),
            raw.get("unit"),
            raw.get("confidence", "medium"),
        )

        valid, _ = validate_fact(fact, artifact_map)

        artifact = artifact_map.get(fact.artifact_id)
        period_check = (
            artifact.metadata.get("period_check")
            if artifact is not None
            else None
        )

        period_eligible = (
            isinstance(period_check, dict)
            and period_check.get("eligible_for_calculation") is True
        )

        if valid and period_eligible:
            facts.append(fact)

    envelope = calculate_support(
        claim,
        artifacts,
        facts,
    )

    provenance = build_provenance_summary(artifacts)

    constraint_graph = build_constraint_graph(
        claim.__dict__,
        artifacts,
        facts,
        envelope,
    )

    resolution = build_resolution_path(
        scenario_name,
        envelope,
    )

    return {
        "scenario": scenario_name,
        "envelope": envelope.__dict__,
        "provenance": provenance,
        "constraint_graph": constraint_graph,
        "resolution_path": resolution,
    }


def build_support_replay(
    scenarios: dict[str, list[Artifact]],
    claim: Claim,
) -> dict[str, Any]:
    """Compare support and binding constraints across demo stages."""

    scenario_order = [
        "baseline",
        "after_manifest",
        "after_shift_record",
    ]

    snapshots = [
        analyze_scenario_deterministically(
            scenario_name,
            scenarios,
            claim,
        )
        for scenario_name in scenario_order
    ]

    transitions = []

    for previous, current in zip(snapshots, snapshots[1:]):
        before = previous["envelope"]
        after = current["envelope"]

        transitions.append({
            "from": previous["scenario"],
            "to": current["scenario"],
            "final_supportable_before_t": before["final_supportable_t"],
            "final_supportable_after_t": after["final_supportable_t"],
            "change_t": round(
                after["final_supportable_t"]
                - before["final_supportable_t"],
                3,
            ),
            "binding_constraint_before": before["binding_constraint"],
            "binding_constraint_after": after["binding_constraint"],
            "receipt_conflict_after": after["receipt_conflict"],
        })

    return {
        "title": "Support Replay",
        "scenarios": [
            snapshot["scenario"]
            for snapshot in snapshots
        ],
        "snapshots": snapshots,
        "transitions": transitions,
    }
