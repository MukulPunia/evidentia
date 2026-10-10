
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from engine.models import Artifact


ALLOWED_EXTENSIONS = {".pdf"}

ARTIFACT_TYPE_RULES = {
    "certificate": "certificate",
    "invoice": "invoice",
    "declaration": "declaration",
    "manifest": "transport_manifest",
    "weighbridge": "weighbridge",
    "facility_profile": "facility_profile",
    "shift_record": "shift_record",
    "receiving_log": "receiving_log",
}

# These identify document records. Facility IDs and claim IDs are not
# treated as document IDs.
_DOCUMENT_REFERENCE_PATTERNS = [
    re.compile(r"(?im)^\s*Document ID\s*:\s*([A-Z0-9][A-Z0-9_-]*)\s*$"),
    re.compile(r"(?im)^\s*Declaration reference\s*:\s*([A-Z0-9][A-Z0-9_-]*)\s*$"),
    re.compile(r"(?im)^\s*Invoice reference\s*:\s*([A-Z0-9][A-Z0-9_-]*)\s*$"),
    re.compile(r"(?im)^\s*Manifest reference\s*:\s*([A-Z0-9][A-Z0-9_-]*)\s*$"),
    re.compile(r"(?im)^\s*Addendum reference\s*:\s*([A-Z0-9][A-Z0-9_-]*)\s*$"),
    re.compile(r"(?im)^\s*Receipt reference\s*:\s*([A-Z0-9][A-Z0-9_-]*)\s*$"),
    re.compile(r"(?im)^\s*Certificate reference\s*:\s*([A-Z0-9][A-Z0-9_-]*)\s*$"),
    re.compile(r"(?im)^\s*Shift reference\s*:\s*([A-Z0-9][A-Z0-9_-]*)\s*$"),
]

_ISSUER_PATTERN = re.compile(
    r"(?im)^\s*Issuer\s*:\s*(.+?)\s*$"
)

_DERIVED_PATTERN = re.compile(
    r"(?i)\bderived\s+from\b[^\r\n]{0,100}?"
    r"\b([A-Z][A-Z0-9_-]*-\d[A-Z0-9_-]*)\b"
)

_PARENT_MANIFEST_PATTERN = re.compile(
    r"(?im)^\s*Parent manifest\s*:?\s*"
    r"([A-Z][A-Z0-9_-]*-\d[A-Z0-9_-]*)\s*$"
)

_DERIVED_FIELD_PATTERN = re.compile(
    r"(?im)^\s*Relationship\s*:?\s*DERIVED_FROM\s+"
    r"([A-Z][A-Z0-9_-]*-\d[A-Z0-9_-]*)\s*$"
)


def infer_artifact_type(filename: str) -> str:
    """Guess the initial document role from its filename."""
    name = Path(filename).stem.lower()

    for keyword, artifact_type in ARTIFACT_TYPE_RULES.items():
        if keyword in name:
            return artifact_type

    return "unknown"


def save_uploaded_file(
    filename: str,
    content: bytes,
    upload_root: Path,
    dossier_id: str | None = None,
) -> dict[str, Any]:
    """Save a PDF safely and calculate its SHA-256 hash."""
    original_name = Path(filename).name

    if not original_name:
        raise ValueError("Uploaded file has no filename.")

    suffix = Path(original_name).suffix.lower()

    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type: {suffix or 'unknown'}"
        )

    if not content:
        raise ValueError("The uploaded file is empty.")

    dossier_id = dossier_id or uuid4().hex
    dossier_directory = upload_root / dossier_id
    dossier_directory.mkdir(parents=True, exist_ok=True)

    digest = hashlib.sha256(content).hexdigest()
    stem = Path(original_name).stem
    destination = dossier_directory / original_name

    # Identical files may reuse the same path. Different files with the
    # same name get separate paths instead of overwriting each other.
    if destination.exists():
        existing_digest = hashlib.sha256(
            destination.read_bytes()
        ).hexdigest()

        if existing_digest != digest:
            destination = (
                dossier_directory
                / f"{stem}__{digest[:12]}{suffix}"
            )

    if not destination.exists():
        destination.write_bytes(content)
    else:
        existing_digest = hashlib.sha256(
            destination.read_bytes()
        ).hexdigest()

        if existing_digest != digest:
            destination = (
                dossier_directory
                / f"{stem}__{digest[:12]}_{uuid4().hex[:6]}{suffix}"
            )
            destination.write_bytes(content)

    return {
        "batch_id": dossier_id,
        "filename": original_name,
        "stored_filename": destination.name,
        "local_path": str(destination),
        "mime_type": "application/pdf",
        "sha256": digest,
        "artifact_type": infer_artifact_type(original_name),
    }


def _document_references(text: str) -> set[str]:
    """Find document references explicitly printed in source text."""
    references: set[str] = set()

    for pattern in _DOCUMENT_REFERENCE_PATTERNS:
        references.update(
            match.group(1).strip().upper()
            for match in pattern.finditer(text or "")
        )

    return references


def _source_class(
    issuer: str,
    text: str,
) -> tuple[str, str]:
    """
    Infer the source category from document text.

    This records what the document says. It does not authenticate
    the issuer or prove that a source is independent.
    """
    issuer_key = re.sub(
        r"[^a-z0-9]+",
        " ",
        issuer.lower(),
    ).strip()

    text_key = (text or "").lower()

    if "greenloop recycling" in issuer_key:
        return (
            "claimant_recycler",
            "Issuer name stated in document; not externally verified",
        )

    if "movefast logistics" in issuer_key:
        return (
            "counterparty",
            "Issuer name stated in document; not externally verified",
        )

    if (
        "plant shift system" in issuer_key
        or "weighbridge system" in issuer_key
    ):
        return (
            "independence_claimed",
            "Document describes a system source; independence not verified",
        )

    if any(
        term in issuer_key
        for term in (
            "environmental protection agency",
            "regulatory authority",
            "pollution control board",
            "regulator",
        )
    ):
        return (
            "regulator_reference_claimed",
            "Issuer name suggests a regulator; not externally verified",
        )

    if "independent" in text_key and issuer:
        return (
            "independence_claimed",
            "Document claims an independent source; not externally verified",
        )

    return (
        "unknown",
        "Source category could not be established from document text",
    )


def infer_upload_provenance(
    artifacts: list[Artifact],
) -> None:
    """
    Extract issuer names and explicit parent-document relationships.

    Relationships are resolved only when a reference identifies one
    unambiguous document in this upload batch.
    """
    reference_to_artifact: dict[str, str] = {}
    reference_counts: dict[str, int] = {}

    # Pass 1: identify each document's declared issuer and references.
    for artifact in artifacts:
        text = artifact.text or ""

        issuer_match = _ISSUER_PATTERN.search(text)
        issuer = (
            issuer_match.group(1).strip()
            if issuer_match
            else "Unknown"
        )

        artifact.issuer = issuer

        origin_class, basis = _source_class(issuer, text)
        artifact.origin_class = origin_class

        references = _document_references(text)
        artifact.metadata["source_document_references"] = sorted(
            references
        )

        artifact.metadata["issuer_extraction_basis"] = (
            "Issuer line extracted from PDF text"
            if issuer != "Unknown"
            else "Issuer not found in PDF text"
        )
        artifact.metadata["origin_class_basis"] = basis

        # Text extraction is not independent source verification.
        artifact.metadata["origin_verified"] = False
        artifact.metadata["independence_verified"] = False
        artifact.metadata["provenance_inferred"] = True

        artifact.derived_from = None

        for reference in references:
            reference_counts[reference] = (
                reference_counts.get(reference, 0) + 1
            )
            reference_to_artifact.setdefault(
                reference,
                artifact.artifact_id,
            )

    # Pass 2: resolve only relationships explicitly stated in the text.
    for artifact in artifacts:
        text = artifact.text or ""
        parent_references: list[str] = []

        parent_references.extend(
            match.group(1).strip().upper()
            for match in _DERIVED_PATTERN.finditer(text)
        )
        parent_references.extend(
            match.group(1).strip().upper()
            for match in _PARENT_MANIFEST_PATTERN.finditer(text)
        )
        parent_references.extend(
            match.group(1).strip().upper()
            for match in _DERIVED_FIELD_PATTERN.finditer(text)
        )

        parent_references = list(dict.fromkeys(parent_references))

        if not parent_references:
            artifact.metadata["provenance_link_status"] = (
                "no_parent_reference_stated"
            )
            continue

        artifact.metadata["declared_parent_references"] = (
            parent_references
        )

        if len(parent_references) != 1:
            artifact.metadata["provenance_link_status"] = (
                "ambiguous_parent"
            )
            continue

        parent_reference = parent_references[0]

        if reference_counts.get(parent_reference, 0) != 1:
            artifact.metadata["provenance_link_status"] = (
                "ambiguous_reference"
            )
            continue

        parent_id = reference_to_artifact.get(parent_reference)

        if not parent_id:
            artifact.metadata["provenance_link_status"] = (
                "parent_not_in_upload_batch"
            )
            artifact.metadata["unresolved_parent_reference"] = (
                parent_reference
            )
            continue

        if parent_id == artifact.artifact_id:
            artifact.metadata["provenance_link_status"] = (
                "self_reference_rejected"
            )
            continue

        artifact.derived_from = parent_id
        artifact.metadata["provenance_link_status"] = (
            "explicit_parent_link"
        )
        artifact.metadata["resolved_parent_reference"] = (
            parent_reference
        )


def create_artifact_from_upload(
    uploaded: dict[str, Any],
    index: int,
) -> Artifact:
    """Convert upload information into a temporary analysis artifact."""
    artifact = Artifact(
        artifact_id=f"UPL-{index:03d}",
        artifact_type=uploaded["artifact_type"],
        filename=uploaded["filename"],
        origin_class="unknown",
        issuer="Unknown",
        local_path=uploaded["local_path"],
        mime_type=uploaded["mime_type"],
        sha256=uploaded["sha256"],
    )

    artifact.metadata["stored_filename"] = uploaded.get(
        "stored_filename",
        uploaded["filename"],
    )
    artifact.metadata["batch_id"] = uploaded.get("batch_id")

    return artifact
