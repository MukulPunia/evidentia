from pathlib import Path

import pytest

from backend.ingestion import (
    create_artifact_from_upload,
    infer_artifact_type,
    save_uploaded_file,
)


def test_infer_known_artifact_types():
    assert (
        infer_artifact_type("recycling_certificate.pdf")
        == "certificate"
    )

    assert (
        infer_artifact_type("transport_manifest.pdf")
        == "transport_manifest"
    )

    assert (
        infer_artifact_type("weighbridge_scan.pdf")
        == "weighbridge"
    )

    assert (
        infer_artifact_type("facility_profile.pdf")
        == "facility_profile"
    )

    assert (
        infer_artifact_type("processing_shift_record.pdf")
        == "shift_record"
    )


def test_unknown_document_type_is_allowed():
    assert (
        infer_artifact_type("some_document.pdf")
        == "unknown"
    )


def test_uploaded_file_is_saved_and_hashed(tmp_path: Path):
    content = b"synthetic evidence"

    result = save_uploaded_file(
        "transport_manifest.pdf",
        content,
        tmp_path,
    )

    saved = Path(
        result["local_path"]
    )

    assert saved.exists()
    assert saved.read_bytes() == content

    assert len(result["sha256"]) == 64
    assert result["mime_type"] == "application/pdf"
    assert result["artifact_type"] == "transport_manifest"


def test_non_pdf_upload_is_rejected(tmp_path: Path):
    with pytest.raises(ValueError):
        save_uploaded_file(
            "malware.exe",
            b"not a pdf",
            tmp_path,
        )


def test_upload_becomes_artifact(tmp_path: Path):
    content = b"synthetic evidence"

    result = save_uploaded_file(
        "facility_profile.pdf",
        content,
        tmp_path,
    )

    artifact = create_artifact_from_upload(
        result,
        1,
    )

    assert artifact.artifact_id == "UPL-001"
    assert artifact.artifact_type == "facility_profile"
    assert artifact.filename == "facility_profile.pdf"
    assert artifact.origin_class == "unknown"
    assert artifact.local_path == result["local_path"]
    assert artifact.sha256 == result["sha256"]