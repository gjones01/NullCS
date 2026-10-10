"""Integration transport/security tests; model outputs are never fabricated here."""
import importlib
import sys
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from main.ui.api.analysis import AnalysisService, clean
from main.ui.api.pipeline_runtime import PipelineFailure, run_process

KEY = 'integration-test-key-' * 3
HEADERS = {'X-NULLCS-KEY': KEY, 'X-NULLCS-OWNER': 'a' * 64}
REPLAY = b'PBDEMS2\x00' + b'0' * 24
REAL_WORK = AnalysisService.work


@pytest.fixture
def client(tmp_path, monkeypatch):
    settings = {
        'NULLCS_ENV': 'production', 'NULLCS_WEB_ANALYSIS': '1', 'NULLCS_DEMO_MODE': '0',
        'NULLCS_API_KEY': KEY, 'NULLCS_FRONTEND_ORIGIN': 'http://localhost:3001',
        'NULLCS_UPLOAD_DIR': str(tmp_path / 'uploads'), 'CLARITY_PROCESSED_DIR': str(tmp_path / 'processed'),
        'NULLCS_WEB_STATE_DIR': str(tmp_path / 'state'), 'NULLCS_WEB_MAX_UPLOAD_BYTES': '1024',
        'NULLCS_WEB_MIN_FREE_BYTES': '0', 'NULLCS_RATE_LIMIT_CAPACITY': '1000',
        'NULLCS_PROJECT_ROOT': str(Path(__file__).resolve().parents[4]),
        'CLARITY_PYTHON_EXE': sys.executable,
        'NULLCS_PIPELINE_EXE': '', 'NULLCS_MODEL_ARTIFACT': '', 'CLARITY_MODEL_ARTIFACT': '',
    }
    for key, value in settings.items():
        monkeypatch.setenv(key, value)
    # Keep transport tests deterministic without invoking or mocking research scoring.
    monkeypatch.setattr(AnalysisService, 'work', lambda self: self.stopping.wait())
    for name in ('main.ui.api.main', 'main.ui.api.config'):
        sys.modules.pop(name, None)
    module = importlib.import_module('main.ui.api.main')
    with TestClient(module.app) as connection:
        yield connection


def reserve(client, **changes):
    return client.post('/api/analysis', headers=HEADERS, json={'filename': 'match.dem', 'size': len(REPLAY), **changes})


def test_owned_upload_and_actual_events(client):
    ticket = reserve(client).json()
    job = ticket['job_id']
    assert client.get(f'/api/analysis/{job}/status', headers=HEADERS).json()['state'] == 'upload_pending'
    response = client.put(ticket['upload_path'], headers={'Authorization': 'Bearer ' + ticket['upload_token'], 'Content-Type': 'application/octet-stream'}, content=REPLAY)
    assert response.status_code == 200
    state = client.get(f'/api/analysis/{job}/status', headers=HEADERS).json()
    assert state['state'] == 'queued'
    assert [e['stage'] for e in state['events']] == ['upload_pending', 'uploading', 'queued']
    assert client.app.state.analysis.source(job).read_bytes() == REPLAY
    assert client.get(f'/api/analysis/{job}/results', headers=HEADERS).status_code == 409
    assert client.put(ticket['upload_path'], headers={'Authorization': 'Bearer ' + ticket['upload_token']}, content=REPLAY).status_code == 409


@pytest.mark.parametrize('metadata', [
    {'filename': '../match.dem'}, {'filename': 'C:\\match.dem'}, {'filename': 'match.zip'},
    {'filename': 'a\x00.dem'}, {'size': 1025}, {'size': '32'}, {'size': True}, {'storage_key': '/etc/passwd'},
])
def test_invalid_metadata(client, metadata):
    assert reserve(client, **metadata).status_code in (413, 422)


def test_authorization_and_enumeration(client):
    ticket = reserve(client).json()
    job = ticket['job_id']
    other = {**HEADERS, 'X-NULLCS-OWNER': 'b' * 64}
    for suffix in ('status', 'results', 'players/123/explanation', 'players/123/evidence/evidence_rt.csv'):
        assert client.get(f'/api/analysis/{job}/{suffix}', headers=other).status_code == 404
        assert client.get(f'/api/analysis/{job}/{suffix}').status_code == 401
    assert client.post(f'/api/analysis/{job}/players/123/explain', headers=other).status_code == 404
    assert client.get('/api/analysis/capabilities', headers={'X-NULLCS-KEY': KEY}).status_code == 401
    assert client.put(ticket['upload_path'], content=REPLAY).status_code == 401
    assert client.put(ticket['upload_path'], headers={'Authorization': 'Bearer wrong'}, content=REPLAY).status_code == 404
    assert client.get('/api/demos', headers=HEADERS).status_code == 404


@pytest.mark.parametrize('body,content_type,expected', [(b'MZ' + b'0'*30, 'application/octet-stream', 400), (REPLAY + b'0', 'application/octet-stream', 413), (REPLAY, 'text/plain', 415)])
def test_failed_upload_cleanup(client, body, content_type, expected):
    ticket = reserve(client).json()
    response = client.put(ticket['upload_path'], headers={'Authorization': 'Bearer '+ticket['upload_token'], 'Content-Type': content_type}, content=body)
    assert response.status_code == expected
    svc = client.app.state.analysis
    assert not svc.partial(ticket['job_id']).exists()
    assert not svc.source(ticket['job_id']).exists()
    assert svc.status(ticket['job_id'], 'a'*64)['state'] == 'failed'


def test_single_worker_lock_and_restart_recovery(client):
    svc = client.app.state.analysis
    with pytest.raises(RuntimeError, match='Only one'):
        AnalysisService(svc.settings).start()
    ticket = reserve(client).json()
    svc.claim_upload(ticket['job_id'], ticket['upload_token'])
    svc.stop()
    svc.start()
    assert svc.owned(ticket['job_id'], 'a'*64)['error_code'] == 'worker_restarted'


def test_public_serialization_removes_diagnostics():
    assert clean({'model_path': 'secret', 'nested': {'v': float('nan')}, 'warning': 'at C:\\private\\file.py'}) == {'nested': {'v': None}, 'warning': 'at [private path]'}


def test_real_pipeline_missing_models_fails_explicitly(client):
    ticket = reserve(client).json()
    job = ticket['job_id']
    client.put(ticket['upload_path'], headers={'Authorization': 'Bearer '+ticket['upload_token'], 'Content-Type': 'application/octet-stream'}, content=REPLAY).raise_for_status()
    svc = client.app.state.analysis
    svc.execute(svc.owned(job, 'a'*64))
    state = client.get(f'/api/analysis/{job}/status', headers=HEADERS).json()
    assert state['state'] == 'failed'
    assert state['error']['code'] == 'model_unavailable'
    assert 'Traceback' not in str(state) and str(svc.settings.PROCESSED_DIR) not in str(state)


def test_expired_ticket_and_capacity(client):
    first = reserve(client).json()
    svc = client.app.state.analysis
    svc.update(first['job_id'], expires=0)
    response = client.put(first['upload_path'], headers={'Authorization': 'Bearer '+first['upload_token']}, content=REPLAY)
    assert response.status_code == 409
    assert reserve(client).status_code == 200
    assert reserve(client).status_code == 429


def test_cors_is_separate_from_authorization(client):
    path = '/api/analysis/capabilities'
    assert client.get(path, headers={'Origin': 'http://localhost:3001'}).status_code == 401
    response = client.options('/api/analysis/unused/upload', headers={'Origin': 'http://localhost:3001', 'Access-Control-Request-Method': 'PUT', 'Access-Control-Request-Headers': 'authorization,content-type'})
    assert response.status_code == 200
    assert response.headers['access-control-allow-origin'] == 'http://localhost:3001'
    rejected = client.options(path, headers={'Origin': 'https://invalid.example', 'Access-Control-Request-Method': 'PUT'})
    assert rejected.status_code == 400


def test_cleanup_error_still_persists_upload_failure(client, monkeypatch):
    ticket = reserve(client).json()
    def denied(*args, **kwargs):
        raise PermissionError('private storage detail')
    monkeypatch.setattr(Path, 'unlink', denied)
    response = client.put(ticket['upload_path'], headers={'Authorization': 'Bearer '+ticket['upload_token'], 'Content-Type': 'application/octet-stream'}, content=b'MZ'+b'0'*30)
    assert response.status_code == 400
    state = client.get(f'/api/analysis/{ticket["job_id"]}/status', headers=HEADERS).json()
    assert state['state'] == 'failed'
    assert 'private storage detail' not in str(state)


def test_older_explanation_is_not_starved_by_new_inference(client, monkeypatch):
    ticket = reserve(client).json()
    svc = client.app.state.analysis
    svc.update(ticket['job_id'], state='queued')
    with svc.db() as db:
        db.execute("INSERT INTO explanations VALUES (?,?,'queued',NULL,?)", (ticket['job_id'], '123', '2000-01-01T00:00:00'))
    dispatched = []
    def explain(row):
        dispatched.append(row['steamid'])
        svc.stopping.set()
    monkeypatch.setattr(svc, 'execute_explanation', explain)
    REAL_WORK(svc)
    assert dispatched == ['123']


def test_real_subprocess_stage_events_and_timeout(tmp_path):
    stages = []
    import os
    run_process([sys.executable, '-u', '-c', "import time; print('[NULLCS_STAGE] parsing'); time.sleep(.3); print('[NULLCS_STAGE] scoring'); time.sleep(.3)"], cwd=tmp_path, env=dict(os.environ), log=tmp_path/'run.log', timeout=5, on_stage=stages.append)
    assert stages == ['parsing', 'scoring']  # no inferred explanation stage
    with pytest.raises(PipelineFailure, match='time limit'):
        run_process([sys.executable, '-c', 'import time; time.sleep(10)'], cwd=tmp_path, env=dict(os.environ), log=tmp_path/'timeout.log', timeout=.1, on_stage=stages.append)


@pytest.mark.parametrize('corrupt', [False, True])
def test_unavailable_explanation_becomes_retryable(client, monkeypatch, corrupt):
    svc = client.app.state.analysis
    job = reserve(client).json()['job_id']
    sid = '123'
    svc.update(job, state='results_ready', stage='results_ready')
    with svc.db() as db:
        db.execute("INSERT INTO explanations VALUES (?,?,'ready',NULL,?)", (job, sid, '2026-01-01'))
    if corrupt:
        path = svc.report_dir(job) / sid / 'web_explanation.json'
        path.parent.mkdir(parents=True)
        path.write_text('{broken json')
    # Isolate explanation storage recovery; no score or ranking is fabricated.
    def player(job_id, owner_id, player_id):
        svc.owned(job_id, owner_id)
        assert player_id == sid
        return {'explanation': {'state': 'ready', 'error': None}}
    monkeypatch.setattr(svc, 'player', player)
    response = client.get(f'/api/analysis/{job}/players/{sid}/explanation', headers=HEADERS)
    assert response.status_code == 200
    assert response.json()['status']['state'] == 'failed'
    assert response.json()['report'] is None
    assert str(svc.root) not in response.text and 'Traceback' not in response.text
    assert svc.owned(job, 'a'*64)['state'] == 'results_ready'
    retry = client.post(f'/api/analysis/{job}/players/{sid}/explain', headers=HEADERS)
    assert retry.json()['state'] == 'queued'


def test_real_explanation_failure_preserves_scoring_state(client):
    svc = client.app.state.analysis
    job = reserve(client).json()['job_id']
    svc.update(job, state='results_ready', stage='results_ready')
    with svc.db() as db:
        db.execute("INSERT INTO explanations VALUES (?,?,'queued',NULL,?)", (job, '123', '2026-01-01'))
    # Execute the real explanation CLI with absent input artifacts, not fake results.
    svc.execute_explanation({'job': job, 'steamid': '123'})
    with svc.db() as db:
        explanation = db.execute('SELECT state,error_message FROM explanations WHERE job=?', (job,)).fetchone()
    assert explanation['state'] == 'failed'
    assert 'Traceback' not in explanation['error_message']
    assert svc.owned(job, 'a'*64)['state'] == 'results_ready'
