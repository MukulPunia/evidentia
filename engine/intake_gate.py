from __future__ import annotations

import re
from typing import Any

from engine.models import Artifact, Claim


# ---------------------------------------------------------------------------
# Recycle Proof Evidence Vocabulary
# ---------------------------------------------------------------------------
# These are positive signals that indicate a document may contain evidence
# relevant to a recycling claim.
#
# Higher weights = stronger evidence-domain signals.
EVIDENCE_TERMS: dict[str, int] = {
    # Core recycling domain
    "recycle": 2,
    "recycling": 3,
    "recycled": 2,
    "recycler": 3,
    "recycling facility": 4,
    "recycling certificate": 4,

    # Waste/material domain
    "waste": 2,
    "e-waste": 4,
    "e waste": 4,
    "electronic waste": 4,
    "scrap": 2,
    "material recovery": 4,
    "recovery": 2,
    "material": 1,

    # Processing / facility
    "processing": 3,
    "processor": 3,
    "processed": 2,
    "facility": 2,
    "capacity": 2,
    "processing capacity": 4,
    "validated processing capacity": 5,
    "shift record": 4,

    # Transport / custody
    "transport": 2,
    "transporter": 3,
    "transport manifest": 5,
    "manifest": 4,
    "shipment": 2,
    "consignment": 2,
    "dispatch": 2,
    "delivery": 2,
    "custody": 2,
    "chain of custody": 5,

    # Receiving / measurement
    "weighbridge": 5,
    "weighbridge scan": 5,
    "receiving": 3,
    "receiving log": 5,
    "receipt": 3,
    "received": 2,
    "weight": 2,
    "net weight": 3,
    "gross weight": 3,
    "mass": 2,
    "quantity": 2,

    # Commercial/supporting evidence
    "certificate": 2,
    "invoice": 2,
    "declaration": 2,
    "claim": 1,
    "consignment note": 4,

    # Units / quantitative evidence
    "ton": 1,
    "tons": 1,
    "tonne": 1,
    "tonnes": 1,
    "kg": 1,
}


# Known document types receive an additional relevance boost.
KNOWN_EVIDENCE_TYPES = {
    "certificate",
    "invoice",
    "declaration",
    "transport_manifest",
    "weighbridge",
    "facility_profile",
    "shift_record",
    "receiving_log",
}


# Terms which are useful for identifying a clearly unrelated document.
# These are NOT the primary relevance mechanism; they are only used to make
# a zero-signal document's exclusion more explainable.
CLEARLY_UNRELATED_TERMS = {
    "marksheet",
    "mark sheet",
    "student academic record",
    "semester examination",
    "semester grades",
    "school transcript",
    "college transcript",
    "course subjects",
}


def _normalize(text: str | None) -> str:
    """Normalize text for robust keyword matching."""
    value = text or ""
    value = value.lower()
    value = value.replace("_", " ")
    value = value.replace("-", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _contains_phrase(text: str, phrase: str) -> bool:
    """
    Match a phrase using word boundaries where possible.
    This avoids accidental matches such as 'kg' inside another word.
    """
    pattern = r"\b" + re.escape(phrase) + r"\b"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def _get_search_text(artifact: Artifact) -> str:
    """
    Combine filename, artifact type, issuer and extracted text.

    Filename/type are useful at intake because a newly uploaded document may
    not yet have gone through Gemini extraction.
    """
    pieces = [
        artifact.filename or "",
        artifact.artifact_type or "",
        artifact.issuer or "",
        artifact.text or "",
    ]

    metadata = getattr(artifact, "metadata", None) or {}

    source_pages = metadata.get("source_pages") or []
    if isinstance(source_pages, list):
        for page in source_pages:
            if isinstance(page, dict):
                pieces.append(str(page.get("text", "")))
            else:
                pieces.append(str(page))

    return _normalize(" ".join(pieces))


def _infer_known_type(artifact: Artifact, normalized_text: str) -> str | None:
    """Infer an evidence type from the artifact metadata/name/text."""
    artifact_type = _normalize(artifact.artifact_type)

    if artifact_type in KNOWN_EVIDENCE_TYPES:
        return artifact_type

    filename = _normalize(artifact.filename)

    filename_type_rules = [
        ("transport_manifest", ("transport manifest", "transport_manifest", "manifest")),
        ("weighbridge", ("weighbridge",)),
        ("facility_profile", ("facility profile", "facility_profile", "facility")),
        ("shift_record", ("shift record", "shift_record")),
        ("receiving_log", ("receiving log", "receiving_log", "receiving")),
        ("certificate", ("certificate",)),
        ("invoice", ("invoice",)),
        ("declaration", ("declaration",)),
    ]

    for inferred_type, phrases in filename_type_rules:
        if any(_contains_phrase(filename, phrase) for phrase in phrases):
            return inferred_type

    # Text-based fallback
    text_rules = [
        ("transport_manifest", ("transport manifest",)),
        ("weighbridge", ("weighbridge",)),
        ("shift_record", ("shift record", "validated processing capacity")),
        ("receiving_log", ("receiving log",)),
        ("certificate", ("recycling certificate",)),
        ("invoice", ("invoice",)),
        ("declaration", ("declaration",)),
        ("facility_profile", ("processing capacity", "facility profile")),
    ]

    for inferred_type, phrases in text_rules:
        if any(_contains_phrase(normalized_text, phrase) for phrase in phrases):
            return inferred_type

    return None


def _score_relevance(
    artifact: Artifact,
) -> tuple[int, list[str], list[str], str | None]:
    """Calculate a transparent relevance score."""
    normalized_text = _get_search_text(artifact)

    score = 0
    signals: list[str] = []
    matched_categories: list[str] = []

    for term, weight in EVIDENCE_TERMS.items():
        if _contains_phrase(normalized_text, term):
            score += weight
            signals.append(term)

    inferred_type = _infer_known_type(artifact, normalized_text)

    if inferred_type:
        type_signal = f"document_type:{inferred_type}"
        signals.append(type_signal)
        score += 3

        category = "known_evidence_document"
        if category not in matched_categories:
            matched_categories.append(category)

    # Categorize the evidence signals.
    category_map = {
        "recycling": {
            "recycle",
            "recycling",
            "recycled",
            "recycler",
            "recycling facility",
            "recycling certificate",
        },
        "waste_material": {
            "waste",
            "e-waste",
            "e waste",
            "electronic waste",
            "scrap",
            "material recovery",
            "recovery",
            "material",
        },
        "processing": {
            "processing",
            "processor",
            "processed",
            "facility",
            "capacity",
            "processing capacity",
            "validated processing capacity",
            "shift record",
        },
        "transport_custody": {
            "transport",
            "transporter",
            "transport manifest",
            "manifest",
            "shipment",
            "consignment",
            "dispatch",
            "delivery",
            "custody",
            "chain of custody",
        },
        "measurement": {
            "weighbridge",
            "weighbridge scan",
            "receiving",
            "receiving log",
            "receipt",
            "received",
            "weight",
            "net weight",
            "gross weight",
            "mass",
            "quantity",
        },
        "commercial_support": {
            "certificate",
            "invoice",
            "declaration",
            "claim",
            "consignment note",
        },
        "quantitative": {
            "ton",
            "tons",
            "tonne",
            "tonnes",
            "kg",
        },
    }

    signal_set = set(signals)

    for category, terms in category_map.items():
        if signal_set.intersection(terms):
            matched_categories.append(category)

    return score, signals, matched_categories, inferred_type


def assess_document_relevance(
    artifact: Artifact,
    claim: Claim,
) -> dict[str, Any]:
    """
    Evidence Intake Gate.

    The gate is intentionally driven by positive evidence-domain signals.
    It does not depend on a long hard-coded list of unrelated academic or
    institutional documents.

    Results:
        accepted -> document contains meaningful recycling-evidence signals
        review   -> relevance is uncertain / insufficiently grounded
        excluded -> document is clearly unrelated and has no evidence signal
    """
    del claim  # Claim context is reserved for future claim-specific scoring.

    normalized_text = _get_search_text(artifact)
    score, signals, categories, inferred_type = _score_relevance(artifact)

    # ------------------------------------------------------------------
    # Strong positive evidence
    # ------------------------------------------------------------------
    if score >= 7:
        confidence = "high"
        status = "accepted"
        reason = (
            "Document contains multiple strong Recycle Proof evidence "
            "signals and appears relevant to the recycling-claim dossier."
        )

    elif score >= 3:
        confidence = "medium"
        status = "accepted"
        reason = (
            "Document contains identifiable Recycle Proof evidence signals, "
            "but its relevance is less strongly established."
        )

    # ------------------------------------------------------------------
    # No meaningful project signals
    # ------------------------------------------------------------------
    else:
        unrelated_hits = [
            term
            for term in CLEARLY_UNRELATED_TERMS
            if _contains_phrase(normalized_text, term)
        ]

        if unrelated_hits:
            status = "excluded"
            confidence = "high"
            reason = (
                "Document contains no meaningful Recycle Proof evidence "
                "signals and appears clearly outside the recycling-evidence "
                "domain."
            )
            signals.extend(
                [f"unrelated:{term}" for term in unrelated_hits]
            )
        else:
            status = "review"
            confidence = "medium"
            reason = (
                "Document does not contain enough Recycle Proof evidence "
                "signals to accept it automatically; human review is required."
            )

    return {
        "status": status,
        "confidence": confidence,
        "score": score,
        "signals": signals,
        "matched_categories": categories,
        "inferred_artifact_type": inferred_type,
        "reason": reason,
        "stamp_required": False,
        "claim_scope": "case_scoped",
    }