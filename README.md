# Evidentia

Evidentia checks whether documents support a recycling claim. It reads uploaded PDFs, checks extracted details against the source pages, and applies clear calculation rules. A reviewer makes the final decision; the app does not declare fraud.

## Run locally

1. Install Python 3.11 or newer.
2. From this folder, install packages:

   ```bash
   python -m pip install -r requirements.txt
   ```

3. Start the app:

   ```bash
   python -m uvicorn backend.main:app --reload
   ```

4. Open http://127.0.0.1:8000. The first start creates the local database and a sample case automatically.

## AI setup (optional)

The sample review can run in demo mode without an API key. For live Gemini extraction, copy `.env.example` to `.env`, set `GEMINI_API_KEY`, and restart the app. Keep your key private.

## Tests

Run the project tests with:

```bash
python -m pytest -q
```

Uploaded PDFs and the local database are created under `data/` when you run the app. They are not bundled. The example evidence PDFs in `data/evidence/` are included.
## Evidence-safety fixes and human-readable export

The release identified by `/api/health` as `2026.10.10-evidence-scope-pdf-1` includes:

- Claim-material scope checks before AI extraction; explicitly unrelated documents are excluded from that claim rather than silently persisted as evidence.
- Quantity calculations begin at zero supported tonnes unless eligible, validated transport or receipt quantity evidence is present. A claim's own amount is not treated as evidence.
- Historical date and reporting-period parsing with the selected facility location used only as a numeric-date-format hint. A contract or publication date is not automatically a shipment date.
- Charts and evidence graphs use the document categories and graph links returned by the analysis, not decorative sample values.
- `POST /api/report.pdf` accepts an analysis-result JSON body and returns a plain-English PDF explaining the claim, eligible quantities, source records, time-period checks, coverage, findings and review steps. Both report-download controls use this endpoint.

Run the test suite with `python -m pytest tests -q`. The release test includes the wrong-material upload path and readable PDF output. Use a separate test case when evaluating unrelated evidence; do not mix unrelated claim material into a live business case.
