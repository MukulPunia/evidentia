
from copy import deepcopy
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

import backend.main as main
from gemini.service import demo_extraction


def prepare_synthetic_evidence(artifacts):
    """Prepare deterministic, source-grounded evidence for unit tests."""
    prepared = deepcopy(artifacts)

    for artifact in prepared:
        artifact.metadata = dict(artifact.metadata or {})
        artifact.metadata.pop("period_check", None)

        source_text = artifact.text or ""

        # Predefined scenario fixtures without dates represent this
        # test claim period. Real uploaded files are not modified here.
        if not any(
            date in source_text
            for date in ("2026-08-01", "2026-08-02")
        ):
            source_text += (
                "\nEvidence period: 2026-08-01 to 2026-08-02"
            )

        artifact.text = source_text
        artifact.metadata["source_pages"] = [
            {"page": 1, "text": source_text}
        ]
        artifact.metadata["page_count"] = 1

    return prepared


def stub_reasoning(_payload):
    """Return predictable reasoning without a live Gemini request."""
    return {
        "status": "test_stub",
        "summary": "Deterministic test response.",
        "alternative_explanations": [],
        "recommended_actions": [],
    }


@pytest.fixture(autouse=True)
def use_deterministic_ai(monkeypatch):
    monkeypatch.setattr(
        main,
        "extract_facts_with_gemini",
        demo_extraction,
    )
    monkeypatch.setattr(
        main,
        "reason_with_gemini",
        stub_reasoning,
    )
    monkeypatch.setattr(
        main,
        "attach_local_evidence",
        prepare_synthetic_evidence,
    )


client = TestClient(main.app)


def test_baseline_math_and_binding_constraint():
    response = client.post(
        "/api/analyze",
        json={"scenario": "baseline"},
    )
    assert response.status_code == 200

    envelope = response.json()["envelope"]

    assert envelope["claimed_t"] == 20.0
    assert envelope["evidence_supported_t"] == 11.2
    assert envelope["final_supportable_t"] == 8.0
    assert envelope["binding_constraint"] == "processing capacity"
    assert envelope["custody_gap_t"] == 7.2
    assert envelope["receipt_conflict"] is True


def test_manifest_does_not_change_final_support():
    baseline = client.post(
        "/api/analyze",
        json={"scenario": "baseline"},
    )
    with_manifest = client.post(
        "/api/analyze",
        json={"scenario": "after_manifest"},
    )

    assert baseline.status_code == 200
    assert with_manifest.status_code == 200

    d0 = baseline.json()
    d1 = with_manifest.json()

    assert (
        d0["envelope"]["final_supportable_t"]
        == d1["envelope"]["final_supportable_t"]
        == 8.0
    )

    assert any(
        item["artifact_id"] == "MAN-03"
        and item["state"] == "verified"
        for item in d1["grounding"]
    )


def test_shift_record_raises_supportable_quantity_to_transport_evidence():
    response = client.post(
        "/api/analyze",
        json={"scenario": "after_shift_record"},
    )
    assert response.status_code == 200

    envelope = response.json()["envelope"]

    assert envelope["final_supportable_t"] == 11.2
    assert (
        envelope["binding_constraint"]
        == "transport/custody evidence"
    )


def test_health():
    assert client.get("/api/health").json()["status"] == "ok"

def test_demo_analysis_does_not_mutate_shared_scenario_templates(monkeypatch):
    before_filename = main.SCENARIOS["baseline"][0].filename
    before_metadata = deepcopy(main.SCENARIOS["baseline"][0].metadata)

    def mutate_request_artifacts(artifacts):
        # Behave like an evidence-attachment step that adds request-specific
        # data. This must affect only the request copy, not the shared fixture.
        artifacts[0].filename = "request-only-mutated.pdf"
        artifacts[0].metadata["request_only_marker"] = True
        return prepare_synthetic_evidence(artifacts)

    monkeypatch.setattr(main, "attach_local_evidence", mutate_request_artifacts)
    response = client.post("/api/analyze", json={"scenario": "baseline"})

    assert response.status_code == 200
    assert main.SCENARIOS["baseline"][0].filename == before_filename
    assert main.SCENARIOS["baseline"][0].metadata == before_metadata

def test_upload_analysis_requires_explicit_case_and_claim():
    response = client.post(
        "/api/analyze-upload",
        files=[("files", ("evidence.pdf", b"%PDF-1.4\\n", "application/pdf"))],
        data={"case_id": "", "claim_id": ""},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Select a case and claim before analyzing evidence."
    )


def test_report_endpoint_returns_readable_pdf():
    analysis = client.post(
        "/api/analyze",
        json={"scenario": "baseline"},
    )
    assert analysis.status_code == 200

    response = client.post("/api/report.pdf", json=analysis.json())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content.startswith(b"%PDF-")

    reader = PdfReader(BytesIO(response.content))
    extracted_text = "\\n".join(
        page.extract_text() or "" for page in reader.pages
    )
    assert "Evidentia Evidence Review" in extracted_text
    assert "Claimed amount" in extracted_text

