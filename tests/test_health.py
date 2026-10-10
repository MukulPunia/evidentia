from fastapi.testclient import TestClient

from backend.main import app


def test_health_identifies_evidence_safety_release():
    response = TestClient(app).get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["build"] == "2026.10.10-evidence-scope-pdf-1"
    assert data["features"]["claim_material_scope_check"] is True
    assert data["features"]["historical_period_validation"] is True
    assert data["features"]["plain_english_pdf_report"] is True
    assert data["features"]["evidence_based_charts"] is True
