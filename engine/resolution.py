from __future__ import annotations

from typing import Any

from .models import SupportEnvelope


def build_resolution_path(
    scenario: str,
    envelope: SupportEnvelope,
) -> dict[str, Any]:
    """
    Build a conditional evidence-resolution path.

    Every action is conditional on the submitted evidence being:
    - valid
    - correctly linked
    - credible for the relevant stage

    This function does not assume that submitting evidence automatically
    increases support.
    """

    actions: list[dict[str, Any]] = []

    if scenario in {
        "baseline",
        "after_manifest",
    }:
        current = envelope.final_supportable_t

        potential_after_shift = min(
            envelope.evidence_supported_t,
            16.0,
        )

        actions.append(
            {
                "action_id": "RES-001",
                "artifact_id": "SHIFT-01",
                "label": "Submit evidence for review",
                "evidence": "processing_shift_record.pdf",
                "stage": "processing",
                "condition": (
                    "Increase is conditional on the shift record being "
                    "validated, linked to FAC-001, and accepted as credible "
                    "processing-system evidence."
                ),
                "current_final_t": current,
                "potential_final_t": potential_after_shift,
                "potential_change_t": round(
                    potential_after_shift - current,
                    3,
                ),
                "current_bottleneck": envelope.binding_constraint,
                "effect": (
                    "May raise the processing-capacity constraint; "
                    "transport evidence can then become the limiting "
                    "supported quantity."
                ),
            }
        )

    if scenario == "baseline":
        actions.append(
            {
                "action_id": "RES-002",
                "artifact_id": "MAN-03",
                "label": "Submit evidence for review",
                "evidence": "transport_manifest_03.pdf",
                "stage": "transport",
                "condition": (
                    "Increase is conditional on the addendum being "
                    "validated and correctly linked to the claimed "
                    "transport event."
                ),
                "current_final_t": envelope.final_supportable_t,
                "potential_final_t": envelope.final_supportable_t,
                "potential_change_t": 0.0,
                "current_bottleneck": envelope.binding_constraint,
                "effect": (
                    "Improves route/linkage evidence but does not "
                    "change the current final support because processing "
                    "capacity remains the binding constraint."
                ),
            }
        )

    if envelope.receipt_conflict:
        actions.append(
            {
                "action_id": "RES-003",
                "artifact_id": "WB-01",
                "label": "Submit evidence for review",
                "evidence": "receiving_log_or_split_shipment_record",
                "stage": "receipt",
                "condition": (
                    "A receiving or split-shipment record must be "
                    "validated and linked to explain the discrepancy "
                    "between receipt and transport quantities."
                ),
                "current_final_t": envelope.final_supportable_t,
                "potential_final_t": None,
                "potential_change_t": None,
                "current_bottleneck": "custody discrepancy",
                "effect": (
                    "May resolve the 18.4 t receipt versus 11.2 t "
                    "transport discrepancy. No automatic increase is "
                    "assumed."
                ),
            }
        )

    return {
        "title": "Evidence Resolution Path",
        "scenario": scenario,
        "current_final_supportable_t": envelope.final_supportable_t,
        "actions": actions,
        "full_chain_status": (
            "pending_review"
            if envelope.receipt_conflict
            else "no_custody_conflict_detected"
        ),
    }