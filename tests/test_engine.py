from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_baseline_math_and_binding_constraint():
    d = client.post('/api/analyze', json={'scenario':'baseline'}).json()
    e = d['envelope']
    assert e['claimed_t'] == 20.0
    assert e['evidence_supported_t'] == 11.2
    assert e['final_supportable_t'] == 8.0
    assert e['binding_constraint'] == 'processing capacity'
    assert e['custody_gap_t'] == 7.2
    assert e['receipt_conflict'] is True

def test_manifest_does_not_change_final_support():
    d0 = client.post('/api/analyze', json={'scenario':'baseline'}).json()
    d1 = client.post('/api/analyze', json={'scenario':'after_manifest'}).json()
    assert d0['envelope']['final_supportable_t'] == d1['envelope']['final_supportable_t'] == 8.0
    assert any(x['artifact_id']=='MAN-03' and x['state']=='verified' for x in d1['grounding'])

def test_shift_record_raises_supportable_quantity_to_transport_evidence():
    d = client.post('/api/analyze', json={'scenario':'after_shift_record'}).json()
    e = d['envelope']
    assert e['final_supportable_t'] == 11.2
    assert e['binding_constraint'] == 'transport/custody evidence'


def test_health():
    assert client.get('/api/health').json()['status'] == 'ok'
