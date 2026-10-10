from io import BytesIO
from pypdf import PdfReader
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_pdf_report_endpoint_returns_readable_pdf_with_weight_explanation():
    payload = {
        "status": "review_required",
        "case_record": {"title": "E-waste Recycling Claim Demo", "ref": "CAS-TEST"},
        "claim_record": {"ref": "CLM-TEST"},
        "claim": {"claim_id": "CLM-TEST", "material": "E-waste", "quantity_t": 20, "period_start": "2026-08-01", "period_end": "2026-08-02"},
        "envelope": {"claimed_t": 20, "evidence_supported_t": 0, "final_supportable_t": 0, "binding_constraint": "transport/custody evidence"},
        "artifacts": [{"artifact_id": "UPL-001", "filename": "27176-Paper-cardboard-recycling.pdf", "artifact_type": "unknown", "text": "Historical material composition total 53,600 tonnes for paper and card."}],
        "intake": [{"artifact_id": "UPL-001", "status": "excluded", "reason": "The selected claim is for electronic waste, but the document identifies paper/cardboard."}],
        "grounding": [{"artifact_id": "UPL-001", "field": "quantity_t", "normalized_value": 53600, "unit": "tonnes", "state": "rejected", "quote": "Total 53,600 100.0%"}],
        "period_validation": {"claim_period": {"start": "2026-08-01", "end": "2026-08-02"}, "in_period_count": 0, "out_of_period_count": 0, "undated_count": 1},
        "extraction_coverage": {"coverage_pct": None, "complete": False},
        "findings": [{"type": "intake_review", "severity": "review", "message": "No document passed the material/scope intake check."}],
    }
    response = client.post("/api/report.pdf", json=payload)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content.startswith(b"%PDF")
    extracted = " ".join(page.extract_text() or "" for page in PdfReader(BytesIO(response.content)).pages)
    assert "SUPPORT NOT ESTABLISHED" in extracted
    assert "53,600 tonnes" in extracted
    assert "not a weight ticket" in extracted
    assert "claim amount" in extracted.lower()
