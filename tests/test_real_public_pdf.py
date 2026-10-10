from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
from pypdf import PdfReader
from io import BytesIO

import backend.main as main
from engine.models import Claim


FIXTURE = Path(__file__).parent / "fixtures" / "27176-Paper-cardboard-recycling.pdf"


def test_real_public_suffolk_pdf_is_excluded_from_ewaste_claim_and_explained(monkeypatch, tmp_path):
    claim = Claim("CLM-TEST", "E-waste", 20.0, "FAC-TEST", "2026-08-01", "2026-08-02", jurisdiction="Gurugram, India")
    case = SimpleNamespace(id="case-id", ref="CAS-TEST", title="E-waste Recycling Claim Demo")
    claim_record = SimpleNamespace(id="claim-id", ref="CLM-TEST")
    monkeypatch.setattr(main, "resolve_case_and_claim", lambda *_args: (case, claim_record, claim))
    monkeypatch.setattr(main, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(main, "extract_facts_with_gemini", lambda *_args: (_ for _ in ()).throw(AssertionError("Gemini must not run for an excluded document")))

    response = TestClient(main.app).post(
        "/api/analyze-upload",
        data={"case_id": "case-id", "claim_id": "claim-id"},
        files={"files": (FIXTURE.name, FIXTURE.read_bytes(), "application/pdf")},
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "review_required"
    assert result["intake"][0]["status"] == "excluded"
    assert result["intake"][0]["material_match"] is False
    assert result["envelope"]["claimed_t"] == 20.0
    assert result["envelope"]["evidence_supported_t"] == 0.0
    assert result["envelope"]["final_supportable_t"] == 0.0
    assert result["persistence"]["artifacts_saved"] == 0
    assert not list((tmp_path / "uploads").rglob("*.pdf"))

    pdf_response = TestClient(main.app).post("/api/report.pdf", json=result)
    assert pdf_response.status_code == 200
    assert pdf_response.headers["content-type"].startswith("application/pdf")
    extracted = " ".join(" ".join((page.extract_text() or "").split()) for page in PdfReader(BytesIO(pdf_response.content)).pages)
    assert "53,600 tonnes" in extracted
    assert "Biffa" in extracted
    assert "Masons MRF" in extracted
    assert "SUPPORT NOT ESTABLISHED" in extracted
    assert "not a weight ticket" in extracted
