from __future__ import annotations

from typing import Any

from .calculator import calculate_support
from .models import Artifact, Claim, Fact
from .provenance import build_provenance_summary
from .constraint_graph import build_constraint_graph
from .resolution import build_resolution_path
from .validator import validate_fact
from gemini.service import demo_extraction


def analyze_scenario_deterministically(
    scenario_name: str,
    scenarios: dict[str, list[Artifact]],
    claim: Claim,
) -> dict[str, Any]:
    """
    Analyze a predefined scenario using the same validation,
    calculation, provenance, graph, and resolution components.

    Replay deliberately uses the local deterministic extraction fixture
    so that a replay comparison does not consume Gemini API calls.
    """

    artifacts = scenarios[scenario_name]

    artifact_dicts = [
        artifact.__dict__
        for artifact in artifacts
    ]

    raw_facts = demo_extraction(
        artifact_dicts
    )

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

        valid, _ = validate_fact(
            fact,
            artifact_map,
        )

        if valid:
            facts.append(fact)

    envelope = calculate_support(
        claim,
        artifacts,
        facts,
    )

    provenance = build_provenance_summary(
        artifacts,
    )

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
    """
    Compare the supported quantity and binding constraint across
    the predefined evidence-resolution stages.
    """

    scenario_order = [
        "baseline",
        "after_manifest",
        "after_shift_record",
    ]

    snapshots = []

    for scenario_name in scenario_order:
        snapshots.append(
            analyze_scenario_deterministically(
                scenario_name,
                scenarios,
                claim,
            )
        )

    transitions = []

    for previous, current in zip(
        snapshots,
        snapshots[1:],
    ):
        previous_envelope = previous["envelope"]
        current_envelope = current["envelope"]

        transitions.append(
            {
                "from": previous["scenario"],
                "to": current["scenario"],
                "final_supportable_before_t": (
                    previous_envelope["final_supportable_t"]
                ),
                "final_supportable_after_t": (
                    current_envelope["final_supportable_t"]
                ),
                "change_t": round(
                    current_envelope["final_supportable_t"]
                    - previous_envelope["final_supportable_t"],
                    3,
                ),
                "binding_constraint_before": (
                    previous_envelope["binding_constraint"]
                ),
                "binding_constraint_after": (
                    current_envelope["binding_constraint"]
                ),
                "receipt_conflict_after": (
                    current_envelope["receipt_conflict"]
                ),
            }
        )

    return {
        "title": "Support Replay",
        "scenarios": [
            snapshot["scenario"]
            for snapshot in snapshots
        ],
        "snapshots": snapshots,
        "transitions": transitions,
    }