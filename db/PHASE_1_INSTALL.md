# Evidentia Phase 1 — Identity + Evidence Database Foundation

This phase adds persistent identity and case-scoped evidence storage without changing the current Gemini analysis endpoint.

## 1. Copy the `db/` folder

Place `db/` at the project root beside `backend/`, `engine/`, `gemini/`, and `frontend/`.

## 2. Add SQLAlchemy

Add this line to `requirements.txt`:

```text
sqlalchemy>=2.0,<3
```

Then run:

```powershell
cd C:\Users\lenovo\Desktop\recycle-proof
py -m pip install "sqlalchemy>=2.0,<3"
```

## 3. Initialize the local database

```powershell
py -m db.bootstrap
```

Expected:

```text
Evidentia database initialized.
```

This creates `data/evidentia.db`.

## 4. Run the new tests

```powershell
py -m pytest tests/test_db_foundation.py -q
```

Expected: `5 passed`.

## What this phase establishes

Internal primary keys are UUID strings. Human-facing references are readable IDs such as `COM-XXXXXXXX`, `FAC-XXXXXXXX`, `CAS-XXXXXXXX`, `CLM-XXXXXXXX`, `ART-XXXXXXXX`, and `FCT-XXXXXXXX`.

Hierarchy: Company → Facility → Case → Claim / Artifact → Fact.

The evidence graph is case-scoped: Case → Evidence Nodes → Evidence Edges.

Exact duplicate files are detected with SHA-256 within a case. Cross-case graph links are rejected.

## Do not change yet

Do not replace `/api/analyze-upload` yet. Do not add automatic company matching yet. Do not send 1,000 documents to Gemini as one prompt. Do not add Neo4j. Do not deploy this database change until the local tests are green.

After this phase, the next APIs will be:

```text
POST /api/companies
POST /api/cases
POST /api/cases/{case_id}/artifacts
GET  /api/cases/{case_id}
GET  /api/cases/{case_id}/graph
```
