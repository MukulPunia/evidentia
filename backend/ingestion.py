from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any
from uuid import uuid4

from engine.models import Artifact


ALLOWED_EXTENSIONS = {
    ".pdf",
}


ARTIFACT_TYPE_RULES = {
    "certificate": "certificate",
    "invoice": "invoice",
    "declaration": "declaration",
    "manifest": "transport_manifest",
    "weighbridge": "weighbridge",
    "facility_profile": "facility_profile",
    "shift_record": "shift_record",
}


def infer_artifact_type(filename: str) -> str:
    """
    Infer an initial document role from the filename.

    This is only a preliminary classification. It is not treated
    as authoritative provenance or document truth.
    """

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
    """
    Save one uploaded evidence file and calculate its SHA-256 hash.

    When dossier_id is supplied, multiple files can belong to the same
    evidence dossier.
    """

    original_name = Path(filename).name

    if not original_name:
        raise ValueError(
            "Uploaded file has no filename."
        )

    suffix = Path(original_name).suffix.lower()

    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type: "
            f"{suffix or 'unknown'}"
        )

    if dossier_id is None:
        dossier_id = uuid4().hex

    dossier_directory = (
        upload_root / dossier_id
    )

    dossier_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    destination = (
        dossier_directory / original_name
    )

    destination.write_bytes(
        content
    )

    sha256 = hashlib.sha256(
        content
    ).hexdigest()

    return {
        "batch_id": dossier_id,
        "filename": original_name,
        "local_path": str(destination),
        "mime_type": "application/pdf",
        "sha256": sha256,
        "artifact_type": infer_artifact_type(
            original_name
        ),
    }

def create_artifact_from_upload(
    uploaded: dict[str, Any],
    index: int,
) -> Artifact:
    """
    Convert upload metadata into a Recycle Proof Artifact.

    Provenance remains unknown until it is explicitly established.
    """

    artifact_id = (
        f"UPL-{index:03d}"
    )

    return Artifact(
        artifact_id=artifact_id,
        artifact_type=uploaded[
            "artifact_type"
        ],
        filename=uploaded[
            "filename"
        ],
        origin_class="unknown",
        issuer="Unknown",
        local_path=uploaded[
            "local_path"
        ],
        mime_type=uploaded[
            "mime_type"
        ],
        sha256=uploaded[
            "sha256"
        ],
    )