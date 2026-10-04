from __future__ import annotations

import hashlib

import mimetypes

from pathlib import Path

from fastapi import (

    FastAPI,

    HTTPException,

    UploadFile,

    File,

)

from fastapi.openapi.utils import get_openapi

from fastapi.middleware.cors import CORSMiddleware

from fastapi.responses import FileResponse

from fastapi.staticfiles import StaticFiles

from pydantic import BaseModel

from engine.models import Artifact, Claim, Fact

from engine.validator import (

    validate_fact,

    validate_extraction_coverage,

)

from engine.document_reader import attach_pdf_source

from engine.calculator import calculate_support

from engine.provenance import build_provenance_summary

from engine.constraint_graph import build_constraint_graph

from engine.resolution import build_resolution_path

from engine.replay import build_support_replay

from engine.intake_gate import assess_document_relevance

from backend.ingestion import save_uploaded_file

from gemini.service import extract_facts_with_gemini, reason_with_gemini

ROOT = Path(__file__).resolve().parents[1]

FRONTEND = ROOT / 'frontend'

EVIDENCE_DIR = ROOT / 'data' / 'evidence'

UPLOAD_DIR = ROOT / 'data' / 'uploads'

app = FastAPI(title='Recycle Proof 4.0', version='0.1.0')

def custom_openapi():

    if app.openapi_schema:

        return app.openapi_schema

    openapi_schema = get_openapi(

        title=app.title,

        version=app.version,

        routes=app.routes,

    )

    def fix_file_schema(value):

        if isinstance(value, dict):

            if value.get("contentMediaType") == "application/octet-stream":

                value.pop("contentMediaType", None)

                value["format"] = "binary"

            for child in value.values():

                fix_file_schema(child)

        elif isinstance(value, list):

            for child in value:

                fix_file_schema(child)

    fix_file_schema(openapi_schema)

    app.openapi_schema = openapi_schema

    return app.openapi_schema

app.openapi = custom_openapi

app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])

class ScenarioRequest(BaseModel):

    scenario: str = 'baseline'

SCENARIOS = {

    'baseline': [

        Artifact(

    'CERT-01',

    'certificate',

    'recycling_certificate.pdf',

    'claimant_recycler',

    'GreenLoop Recycling',

    'Certified quantity: 20.0 t',

    derived_from='DEC-01',

),

        Artifact('INV-01','invoice','recycler_invoice.pdf','claimant_recycler','GreenLoop Recycling','Invoice quantity: 20.0 t', derived_from='DEC-01'),

        Artifact('DEC-01','declaration','recycler_declaration.pdf','claimant_recycler','GreenLoop Recycling','Recycler declaration: 20.0 t'),

        Artifact('MAN-01','transport_manifest','transport_manifest.pdf','counterparty','MoveFast Logistics','Net transported quantity: 11.2 t'),

        Artifact('WB-01','weighbridge','weighbridge_scan.pdf','independent_system','WeighBridge System','Net weight: 18.4 t'),

        Artifact('FAC-01','facility_profile','facility_profile.pdf','claimant_recycler','GreenLoop Recycling','Declared processing capacity during period: 8.0 t'),

    ],

    'after_manifest': [

       Artifact(

    'CERT-01',

    'certificate',

    'recycling_certificate.pdf',

    'claimant_recycler',

    'GreenLoop Recycling',

    'Certified quantity: 20.0 t',

    derived_from='DEC-01',

),

        Artifact('INV-01','invoice','recycler_invoice.pdf','claimant_recycler','GreenLoop Recycling','Invoice quantity: 20.0 t', derived_from='DEC-01'),

        Artifact('DEC-01','declaration','recycler_declaration.pdf','claimant_recycler','GreenLoop Recycling','Recycler declaration: 20.0 t'),

        Artifact('MAN-01','transport_manifest','transport_manifest.pdf','counterparty','MoveFast Logistics','Net transported quantity: 11.2 t'),

        Artifact('MAN-03','transport_manifest','transport_manifest_03.pdf','counterparty','MoveFast Logistics','Route addendum for Manifest 01; linked quantity: 11.2 t', derived_from='MAN-01'),

        Artifact('WB-01','weighbridge','weighbridge_scan.pdf','independent_system','WeighBridge System','Net weight: 18.4 t'),

        Artifact('FAC-01','facility_profile','facility_profile.pdf','claimant_recycler','GreenLoop Recycling','Declared processing capacity during period: 8.0 t'),

    ],

    'after_shift_record': [

        Artifact(

    'CERT-01',

    'certificate',

    'recycling_certificate.pdf',

    'claimant_recycler',

    'GreenLoop Recycling',

    'Certified quantity: 20.0 t',

    derived_from='DEC-01',

),

        Artifact('INV-01','invoice','recycler_invoice.pdf','claimant_recycler','GreenLoop Recycling','Invoice quantity: 20.0 t', derived_from='DEC-01'),

        Artifact('DEC-01','declaration','recycler_declaration.pdf','claimant_recycler','GreenLoop Recycling','Recycler declaration: 20.0 t'),

        Artifact('MAN-01','transport_manifest','transport_manifest.pdf','counterparty','MoveFast Logistics','Net transported quantity: 11.2 t'),

        Artifact('WB-01','weighbridge','weighbridge_scan.pdf','independent_system','WeighBridge System','Net weight: 18.4 t'),

        Artifact('FAC-01','facility_profile','facility_profile.pdf','claimant_recycler','GreenLoop Recycling','Declared processing capacity during period: 8.0 t'),

        Artifact('SHIFT-01','shift_record','processing_shift_record.pdf','independent_system','Plant Shift System','Valid processing shift evidence: 16.0 t capacity for stated period'),

    ],

}

def attach_local_evidence(

    artifacts: list[Artifact],

) -> list[Artifact]:

    """Attach real local evidence files and extract their source text."""

    for artifact in artifacts:

        path = EVIDENCE_DIR / artifact.filename

        if not path.exists():

            continue

        artifact.local_path = str(path)

        artifact.mime_type = (

            mimetypes.guess_type(path.name)[0]

            or 'application/octet-stream'

        )

        artifact.sha256 = hashlib.sha256(path.read_bytes()).hexdigest()

        attach_pdf_source(artifact)

    return artifacts

def prepare_uploaded_artifact(artifact: Artifact) -> Artifact:

    """Attach upload metadata and extract actual PDF source text."""

    if artifact.local_path:

        path = Path(artifact.local_path)

        if path.exists():

            artifact.mime_type = artifact.mime_type or (

                mimetypes.guess_type(path.name)[0] or 'application/pdf'

            )

            artifact.sha256 = artifact.sha256 or hashlib.sha256(

                path.read_bytes()

            ).hexdigest()

            attach_pdf_source(artifact)

    return artifact

@app.get('/api/health')

def health():

    return {

        'status': 'ok',

        'service': 'recycle-proof',

    }

@app.post('/api/upload')

async def upload_dossier(

    files: list[UploadFile] = File(...),

):

    if not files:

        raise HTTPException(

            400,

            'No evidence files supplied.',

        )

    dossier_id = __import__('uuid').uuid4().hex

    uploaded = []

    for upload in files:

        if not upload.filename:

            continue

        content = await upload.read()

        try:

            result = save_uploaded_file(

                upload.filename,

                content,

                UPLOAD_DIR,

                dossier_id,

            )

        except ValueError as exc:

            raise HTTPException(

                400,

                str(exc),

            ) from exc

        uploaded.append(result)

    if not uploaded:

        raise HTTPException(

            400,

            'No valid PDF evidence files supplied.',

        )

    return {

        'dossier_id': dossier_id,

        'document_count': len(uploaded),

        'documents': uploaded,

    }

@app.post('/api/analyze-upload')

async def analyze_upload(

    files: list[UploadFile] = File(...),

):

    """Analyze a real uploaded evidence dossier through the production path."""

    if not files:

        raise HTTPException(

            status_code=400,

            detail='At least one evidence document is required.',

        )

    dossier_id = __import__('uuid').uuid4().hex

    claim = Claim(

        'CLM-UPLOAD-001',

        'e-waste',

        20.0,

        'FAC-001',

        '2026-08-01',

        '2026-08-02',

    )

    artifacts: list[Artifact] = []

    intake_results: list[dict] = []

    # 1. Save uploads and attach source text.

    # 1. Save uploads and attach source text.

    for index, upload in enumerate(files, 1):

        if not upload.filename:

            continue

        content = await upload.read()

        try:

            saved = save_uploaded_file(

                upload.filename,

                content,

                UPLOAD_DIR,

                dossier_id,

            )

        except ValueError as exc:

            raise HTTPException(

                status_code=400,

                detail=str(exc),

            ) from exc

        artifact = Artifact(

            f"UPL-{index:03d}",

            saved["artifact_type"],

            saved["filename"],

            "unknown",

            "Unknown",

            "",

        )

        artifact.local_path = saved["local_path"]

        artifact.mime_type = saved.get("mime_type")

        artifact.sha256 = saved.get("sha256")

        attach_pdf_source(artifact)

        artifacts.append(artifact)

    if not artifacts:

        raise HTTPException(

            status_code=400,

            detail="No valid PDF evidence files supplied.",

        )

    # 2. Evidence Intake Gate.

    accepted_artifacts: list[Artifact] = []

    review_artifacts: list[Artifact] = []

    excluded_artifacts: list[Artifact] = []

    for artifact in artifacts:

        result = assess_document_relevance(artifact, claim)

        intake_results.append({

            'artifact_id': artifact.artifact_id,

            'filename': artifact.filename,

            **result,

        })

        if result['status'] == 'accepted':

            accepted_artifacts.append(artifact)

        elif result['status'] == 'review':

            review_artifacts.append(artifact)

        else:

            excluded_artifacts.append(artifact)

    if not accepted_artifacts:

        return {

            'status': 'review_required',

            'dossier_id': dossier_id,

            'claim': claim.__dict__,

            'artifacts': [a.__dict__ for a in artifacts],

            'intake': intake_results,

            'review_artifacts': [a.__dict__ for a in review_artifacts],

            'excluded_artifacts': [a.__dict__ for a in excluded_artifacts],

            'message': (

                'No uploaded document was accepted automatically by the '

                'Recycle Proof Evidence Intake Gate.'

            ),

        }

    # 3. Gemini #1: source-grounded extraction from accepted evidence only.

    try:

        raw_facts = extract_facts_with_gemini(

            [a.__dict__ for a in accepted_artifacts]

        )

    except Exception as exc:

        raise HTTPException(

            status_code=502,

            detail=f'Gemini extraction failed: {exc}',

        ) from exc

    # 4. Coverage + fact grounding.

    coverage = validate_extraction_coverage(

        accepted_artifacts,

        raw_facts,

    )

    artifacts_map = {

        a.artifact_id: a

        for a in accepted_artifacts

    }

    facts: list[Fact] = []

    grounding: list[dict] = []

    for i, rf in enumerate(raw_facts, 1):

        try:

            fact = Fact(

                f'FCT-UP-{i:03d}',

                rf['artifact_id'],

                int(rf.get('page', 1)),

                rf['field'],

                rf['quote'],

                rf.get('normalized_value'),

                rf.get('unit'),

                rf.get('confidence', 'medium'),

            )

        except (KeyError, TypeError, ValueError) as exc:

            grounding.append({

                'fact_id': f'FCT-UP-{i:03d}',

                'state': {

                    'verified': False,

                    'reason': f'Invalid Gemini fact schema: {exc}',

                },

            })

            continue

        ok, state = validate_fact(fact, artifacts_map)

        grounding.append({

            'fact_id': fact.fact_id,

            'artifact_id': fact.artifact_id,

            'state': state,

            'field': fact.field,

            'quote': fact.quote,

            'normalized_value': fact.normalized_value,

            'unit': fact.unit,

            'confidence': fact.confidence,

        })

        if ok:

            facts.append(fact)

    # 5. Deterministic evidence engine.

    envelope = calculate_support(

        claim,

        accepted_artifacts,

        facts,

    )

    # 6. Provenance / independence.

    provenance = build_provenance_summary(

        accepted_artifacts,

    )

    # 7. Findings.
    findings: list[dict] = []

    if envelope.receipt_conflict:
        receipt_ids = [
            artifact.artifact_id
            for artifact in accepted_artifacts
            if artifact.artifact_type == "weighbridge"
        ]
        transport_ids = [
            artifact.artifact_id
            for artifact in accepted_artifacts
            if artifact.artifact_type == "transport_manifest"
        ]
        findings.append({
            "type": "custody_conflict",
            "severity": "review",
            "message": (
                "Receipt evidence exceeds linked transport evidence. "
                "The custody discrepancy requires human verification."
            ),
            "source_artifacts": receipt_ids + transport_ids,
        })

    findings.append({
        "type": "binding_constraint",
        "severity": "constraint",
        "message": f"Binding constraint: {envelope.binding_constraint}",
        "source_artifacts": [],
    })

    if not coverage["complete"]:
        missing = [
            item["artifact_id"]
            for item in coverage["artifacts"]
            if item["status"] == "no_fact_extracted"
        ]
        findings.append({
            "type": "extraction_coverage_gap",
            "severity": "review",
            "message": "One or more accepted artifacts produced no extracted fact.",
            "source_artifacts": missing,
        })

    if review_artifacts:
        findings.append({
            "type": "intake_review",
            "severity": "review",
            "message": "One or more uploaded documents require human intake review.",
            "source_artifacts": [
                artifact.artifact_id
                for artifact in review_artifacts
            ],
        })

    # 8. Case-scoped constraint graph.

    constraint_graph = build_constraint_graph(

        claim.__dict__,

        accepted_artifacts,

        facts,

        envelope,

    )

    # 9. Resolution path.

    resolution_path = build_resolution_path(

        'baseline',

        envelope,

    )

    # 10. Gemini #2: bounded reasoning.

    reasoning_input = {

        'claim': claim.__dict__,

        'envelope': envelope.__dict__,

        'findings': findings,

        'grounding': grounding,

        'extraction_coverage': coverage,

        'provenance': provenance,

        'constraint_graph': constraint_graph,

        'resolution_path': resolution_path,

    }

    try:

        reasoning = reason_with_gemini(reasoning_input)

    except Exception as exc:

        reasoning = {

            'status': 'unavailable',

            'message': str(exc),

        }

    return {

        'status': 'analyzed',

        'dossier_id': dossier_id,

        'claim': claim.__dict__,

        'artifacts': [

            a.__dict__

            for a in artifacts

        ],

        'intake': intake_results,

        'review_artifacts': [

            a.__dict__

            for a in review_artifacts

        ],

        'excluded_artifacts': [

            a.__dict__

            for a in excluded_artifacts

        ],

        'grounding': grounding,

        'extraction_coverage': coverage,

        'envelope': envelope.__dict__,

        'findings': findings,

        'provenance': provenance,

        'constraint_graph': constraint_graph,

        'resolution_path': resolution_path,

        'gemini_reasoning': reasoning,

    }

@app.post('/api/analyze')
def analyze(req: ScenarioRequest):
    artifacts = SCENARIOS.get(req.scenario)
    if artifacts is None:
        raise HTTPException(404, 'Unknown scenario')

    claim = Claim(
        'CLM-001',
        'e-waste',
        20.0,
        'FAC-001',
        '2026-08-01',
        '2026-08-02',
    )

    artifacts = attach_local_evidence(artifacts)
    artifact_dicts = [a.__dict__ for a in artifacts]

    raw_facts = extract_facts_with_gemini(artifact_dicts)

    coverage = validate_extraction_coverage(
        artifacts,
        raw_facts,
    )

    artifacts_map = {
        a.artifact_id: a
        for a in artifacts
    }

    facts: list[Fact] = []
    grounding: list[dict] = []

    for i, rf in enumerate(raw_facts, 1):
        try:
            fact = Fact(
                f'FCT-{i:03d}',
                rf['artifact_id'],
                int(rf.get('page', 1)),
                rf['field'],
                rf['quote'],
                rf.get('normalized_value'),
                rf.get('unit'),
                rf.get('confidence', 'medium'),
            )
        except (KeyError, TypeError, ValueError) as exc:
            grounding.append({
                'fact_id': f'FCT-{i:03d}',
                'state': {
                    'verified': False,
                    'reason': f'Invalid Gemini fact schema: {exc}',
                },
            })
            continue

        ok, state = validate_fact(
            fact,
            artifacts_map,
        )

        grounding.append({
            'fact_id': fact.fact_id,
            'artifact_id': fact.artifact_id,
            'state': state,
            'field': fact.field,
            'quote': fact.quote,
            'normalized_value': fact.normalized_value,
            'unit': fact.unit,
            'confidence': fact.confidence,
        })

        if ok:
            facts.append(fact)

    envelope = calculate_support(
        claim,
        artifacts,
        facts,
    )

    provenance = build_provenance_summary(
        artifacts,
    )

    findings: list[dict] = []

    if envelope.receipt_conflict:
        findings.append({
            'type': 'custody_conflict',
            'severity': 'review',
            'message': (
                'Receipt evidence exceeds the linked transport evidence.'
            ),
            'source_artifacts': [
                'WB-01',
                'MAN-01',
            ],
        })

    findings.append({
        'type': 'binding_constraint',
        'severity': 'constraint',
        'message': f'Binding constraint: {envelope.binding_constraint}',
        'source_artifacts': ['FAC-01'],
    })

    if not coverage['complete']:
        missing = [
            item['artifact_id']
            for item in coverage['artifacts']
            if item['status'] == 'no_fact_extracted'
        ]
        findings.append({
            'type': 'extraction_coverage_gap',
            'severity': 'review',
            'message': (
                'One or more submitted artifacts produced '
                'no extracted fact.'
            ),
            'source_artifacts': missing,
        })

    constraint_graph = build_constraint_graph(
        claim.__dict__,
        artifacts,
        facts,
        envelope,
    )

    resolution_path = build_resolution_path(
        req.scenario,
        envelope,
    )

    reasoning = reason_with_gemini({
        'claim': claim.__dict__,
        'envelope': envelope.__dict__,
        'findings': findings,
        'grounding': grounding,
        'extraction_coverage': coverage,
        'provenance': provenance,
        'constraint_graph': constraint_graph,
        'resolution_path': resolution_path,
    })

    return {
        'claim': claim.__dict__,
        'artifacts': [a.__dict__ for a in artifacts],
        'grounding': grounding,
        'extraction_coverage': coverage,
        'envelope': envelope.__dict__,
        'findings': findings,
        'provenance': provenance,
        'constraint_graph': constraint_graph,
        'resolution_path': resolution_path,
        'gemini_reasoning': reasoning,
    }

@app.get('/api/replay')

def replay():

    claim = Claim(

        'CLM-001',

        'e-waste',

        20.0,

        'FAC-001',

        '2026-08-01',

        '2026-08-02',

    )

    return build_support_replay(

        SCENARIOS,

        claim,

    )

app.mount('/static', StaticFiles(directory=FRONTEND), name='static')

@app.get('/')

def index():

    return FileResponse(FRONTEND / 'index.html')
