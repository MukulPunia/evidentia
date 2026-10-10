
from __future__ import annotations

from typing import Any

from .models import SupportEnvelope


def _binding_description(binding_constraint: str) -> str:
    """Return simple wording for the limit identified by the calculation."""
    labels = {
        "processing capacity": "processing capacity",
        "transport/custody evidence": "transport records",
        "receipt/custody evidence": "receiving records",
        "none identified": "no single limit identified",
    }
    return labels.get(
        binding_constraint,
        binding_constraint or "the current evidence",
    )


def build_resolution_path(
    scenario: str,
    envelope: SupportEnvelope,
) -> dict[str, Any]:
    """
    Build a list of possible next steps based on the calculated support limit.

    Adding a document does not automatically increase the supported amount.
    Evidence must be checked, linked to the correct claim, and accepted
    as credible for the relevant stage.
    """

    actions: list[dict[str, Any]] = []
    current = envelope.final_supportable_t
    current_limit = _binding_description(envelope.binding_constraint)

    if scenario in {"baseline", "after_manifest"}:
        potential_after_shift = min(
            envelope.evidence_supported_t,
            16.0,
        )

        if envelope.binding_constraint == "processing capacity":
            shift_effect = (
                "A valid processing shift record may increase the supported "
                "amount, provided no other evidence limit is lower."
            )
        else:
            shift_effect = (
                f"The current limit is {current_limit}. "
                "A processing shift record alone will not increase the "
                "supported amount while this limit remains unchanged."
            )

        actions.append(
            {
                "action_id": "RES-001",
                "artifact_id": "SHIFT-01",
                "label": "Submit evidence for review",
                "evidence": "processing_shift_record.pdf",
                "stage": "processing",
                "condition": (
                    "The shift record must be checked, linked to the correct "
                    "facility, and accepted as credible processing evidence."
                ),
                "current_final_t": current,
                "potential_final_t": potential_after_shift,
                "potential_change_t": round(
                    potential_after_shift - current,
                    3,
                ),
                "current_bottleneck": envelope.binding_constraint,
                "effect": shift_effect,
            }
        )

    if scenario == "baseline":
        if envelope.binding_constraint == "transport/custody evidence":
            manifest_effect = (
                "Transport records currently limit the supported amount. "
                "This add-on may clarify the route, but will not increase "
                "support unless it provides validated, additional quantity "
                "evidence."
            )
        else:
            manifest_effect = (
                f"The current limit is {current_limit}. "
                "This add-on may clarify the transport route, but no increase "
                "is assumed unless relevant new evidence is checked and "
                "linked to the claim."
            )

        actions.append(
            {
                "action_id": "RES-002",
                "artifact_id": "MAN-03",
                "label": "Submit evidence for review",
                "evidence": "transport_manifest_03.pdf",
                "stage": "transport",
                "condition": (
                    "The add-on must be checked and linked to the correct "
                    "transport event."
                ),
                "current_final_t": current,
                "potential_final_t": current,
                "potential_change_t": 0.0,
                "current_bottleneck": envelope.binding_constraint,
                "effect": manifest_effect,
            }
        )

    if envelope.receipt_conflict:
        actions.append(
            {
                "action_id": "RES-003",
                "artifact_id": "WB-01",
                "label": "Provide receiving or split-shipment records",
                "evidence": "receiving_log_or_split_shipment_record",
                "stage": "receipt",
                "condition": (
                    "The receiving or split-shipment record must be checked "
                    "and linked to explain the difference between the "
                    "recorded receipt and transport quantities."
                ),
                "current_final_t": current,
                "potential_final_t": None,
                "potential_change_t": None,
                "current_bottleneck": "custody discrepancy",
                "effect": (
                    "The receipt records 18.4 tonnes while the linked "
                    "transport record supports 11.2 tonnes. Additional "
                    "evidence may explain the difference, but no automatic "
                    "increase in support is assumed."
                ),
            }
        )

    return {
        "title": "Evidence Resolution Path",
        "scenario": scenario,
        "current_final_supportable_t": current,
        "actions": actions,
        "full_chain_status": (
            "pending_review"
            if envelope.receipt_conflict
            else "no_custody_conflict_detected"
        ),
    }
