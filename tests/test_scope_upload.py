from io import BytesIO
from types import SimpleNamespace

from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

import backend.main as main
from engine.models import Claim


def _pdf(text: str) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf)
    for line_no, line in enumerate(text.splitlines(), start=1):
        c.drawString(45, 800 - line_no * 18, line[:110])
    c.save()
    return buf.getvalue()


def test_upload_excludes_wrong_material_without_saving_it_to_the_claim(monkeypatch, tmp_path):
    claim = Claim("CLM-TEST", "e-waste", 20.0, "FAC-TEST", "2026-08-01", "2026-08-02")
    case = SimpleNamespace(id="case-id", ref="CAS-TEST", title="E-waste demo")
    claim_record = SimpleNamespace(id="claim-id", ref="CLM-TEST")
    monkeypatch.setattr(main, "resolve_case_and_claim", lambda *_args: (case, claim_record, claim))
    monkeypatch.setattr(main, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(main, "extract_facts_with_gemini", lambda *_args: (_ for _ in ()).throw(AssertionError("Gemini must not run for an excluded document")))

    client = TestClient(main.app)
    content = _pdf("Suffolk County Council paper and cardboard recycling contract\nHistorical material total: 53,600 tonnes\nPaper, card, plastics and metals")
    response = client.post(
        "/api/analyze-upload",
        data={"case_id": "case-id", "claim_id": "claim-id"},
        files={"files": ("27176-Paper-cardboard-recycling.pdf", content, "application/pdf")},
    )

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "review_required"
    assert result["envelope"]["claimed_t"] == 20.0
    assert result["envelope"]["evidence_supported_t"] == 0.0
    assert result["envelope"]["final_supportable_t"] == 0.0
    assert result["persistence"]["artifacts_saved"] == 0
    assert result["excluded_artifacts"]
    assert result["intake"][0]["material_match"] is False
    assert not list((tmp_path / "uploads").rglob("*.pdf"))
