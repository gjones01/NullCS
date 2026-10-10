import importlib
import json
import sys
from pathlib import Path
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from main.ui.api.desktop_result import read_result


def fixture(root, calibrated=True):
    root.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([
        dict(demo_id='TEST_report', map_name='de_inferno', attacker_steamid='76561198000000002', attacker_name='<script>', risk=.7, proba_cheater_infer=.5, proba_calibrated=.7 if calibrated else None, confidence=.8),
        dict(demo_id='TEST_report', map_name='de_inferno', attacker_steamid='76561198000000001', attacker_name='Player', risk=.2, proba_cheater_infer=.9, proba_calibrated=.2 if calibrated else None, confidence=.6),
    ]).to_csv(root/'ranked_players_infer.csv',index=False)
    (root/'infer_manifest.json').write_text(json.dumps(dict(demo_id='TEST_report', parser_provenance={'demoparser2_version':'0.41.4'})))
    (root/'debug_score_trace.json').write_text(json.dumps(dict(calibration_used=calibrated, model_artifact_path='private/path/model.json',model_sha256='abc')))


def test_preserves_canonical_order_and_scores(tmp_path):
    fixture(tmp_path)
    result=read_result(tmp_path,'TEST_report','match.dem')
    assert [p['model_score'] for p in result['players']] == [.5,.9]
    assert [p['review_score'] for p in result['players']] == [.7,.2]
    assert [p['rank'] for p in result['players']] == [1,2]
    assert result['players'][0]['name']=='<script>'
    assert 'private/path' not in json.dumps(result)
    assert 'explanation' not in result
    assert any('stale' in w for w in result['warnings'])


def test_no_manufactured_calibration(tmp_path):
    fixture(tmp_path,False)
    assert all(p['calibrated_probability'] is None for p in read_result(tmp_path,'TEST_report','m.dem')['players'])


def test_mismatched_artifact_rejected(tmp_path):
    fixture(tmp_path)
    with pytest.raises(ValueError): read_result(tmp_path,'TEST_other','m.dem')


def test_missing_score_rejected(tmp_path):
    fixture(tmp_path)
    data=pd.read_csv(tmp_path/'ranked_players_infer.csv'); data.loc[0,'risk']=float('nan'); data.to_csv(tmp_path/'ranked_players_infer.csv',index=False)
    with pytest.raises(ValueError): read_result(tmp_path,'TEST_report','m.dem')


@pytest.fixture
def desktop(tmp_path, monkeypatch):
    for key,value in dict(NULLCS_ENV='desktop',NULLCS_DESKTOP_MODE='1',NULLCS_DESKTOP_KEY='test-only-key',NULLCS_WEB_ANALYSIS='0',NULLCS_DEMO_MODE='0',CLARITY_PROCESSED_DIR=str(tmp_path/'processed'),NULLCS_STATE_DIR=str(tmp_path/'state'),NULLCS_UPLOAD_DIR=str(tmp_path/'uploads'),NULLCS_MAX_UPLOAD_BYTES='64').items(): monkeypatch.setenv(key,value)
    for name in ('main.ui.api.main','main.ui.api.config'): sys.modules.pop(name,None)
    api=importlib.import_module('main.ui.api.main')
    with TestClient(api.app) as client: yield api,client
    for name in ('main.ui.api.main','main.ui.api.config'): sys.modules.pop(name,None)


def test_desktop_auth_and_result(desktop,tmp_path):
    api,client=desktop
    fixture(api.REPORTS_DIR/'TEST_report')
    api._set_job('TEST_report',state='done',original_filename='match.dem')
    endpoint='/api/desktop/demo/TEST_report/result'
    assert client.get(endpoint).status_code==401
    result=client.get(endpoint,headers={'X-NULLCS-KEY':'test-only-key'})
    assert result.status_code==200
    assert len(result.json()['players'])==2
    assert client.get('/api/desktop/demo/../result',headers={'X-NULLCS-KEY':'test-only-key'}).status_code!=200


@pytest.mark.parametrize('content,status',[(b'MZbad',400),(b'PBDEMS2\x00'+b'x'*80,413)])
def test_invalid_local_demo(desktop,tmp_path,content,status):
    _,client=desktop
    path=tmp_path/'bad.dem';path.write_bytes(content)
    response=client.post('/api/demo/from-path',json={'path':str(path)},headers={'X-NULLCS-KEY':'test-only-key'})
    assert response.status_code==status


def test_launch_failure_becomes_error(desktop,tmp_path,monkeypatch):
    api,_=desktop
    def fail(*args,**kwargs): raise OSError('private diagnostic')
    monkeypatch.setattr(api.subprocess,'Popen',fail)
    api._run_pipeline_background('TEST_failure',tmp_path/'input.dem')
    job=api._get_job('TEST_failure')
    assert job['state']=='error'
    assert 'private diagnostic' not in job['error']


def test_sidecar_forwards_research_flags(monkeypatch):
    from main.ui.api import desktop_sidecar
    import threading
    captured = []
    monkeypatch.setattr(sys, 'argv', ['backend.exe', 'run-infer', '--dem_path', 'demo.dem', '--demo_id', 'TEST_a'])
    monkeypatch.setattr(threading.Thread, 'start', lambda self: None)
    monkeypatch.setattr(desktop_sidecar, '_run_module_main', lambda name, args: captured.append((name,args)) or 0)
    assert desktop_sidecar.main() == 0
    assert captured == [('main.scripts.run_infer_pipeline', ['--dem_path','demo.dem','--demo_id','TEST_a'])]


@pytest.mark.parametrize('payload', [
    {'path': ['not-a-string']}, {'path': 'match.dem', 'demo_id': 'TEST_existing'},
    {'path': ''}, {'path': 'match.dem', 'extra': True},
])
def test_local_intake_rejects_malformed_or_client_job_ids(desktop, payload):
    _, client = desktop
    response = client.post('/api/demo/from-path', json=payload, headers={'X-NULLCS-KEY': 'test-only-key'})
    assert response.status_code == 422


@pytest.mark.parametrize('path', ['\\\\server\\share\\demo.dem', '//server/share/demo.dem', '\\\\?\\C:\\demo.dem', 'bad\x00.dem'])
def test_local_intake_rejects_network_and_device_paths(desktop, path):
    _, client = desktop
    response = client.post('/api/demo/from-path', json={'path': path}, headers={'X-NULLCS-KEY': 'test-only-key'})
    assert response.status_code == 400


def test_desktop_internal_errors_do_not_disclose_diagnostics(desktop):
    api, _ = desktop
    @api.app.get('/api/test-internal-failure')
    def fail():
        raise RuntimeError('private-path-or-secret')
    with TestClient(api.app, raise_server_exceptions=False) as client:
        response = client.get('/api/test-internal-failure', headers={'X-NULLCS-KEY': 'test-only-key'})
    assert response.status_code == 500
    assert 'private-path-or-secret' not in response.text


def test_local_intake_assigns_distinct_ids(desktop, tmp_path, monkeypatch):
    api, client = desktop
    from types import SimpleNamespace
    # Stub only the API's launcher, not TestClient/AnyIO's worker threads.
    monkeypatch.setattr(api, 'threading', SimpleNamespace(Thread=lambda **kwargs: SimpleNamespace(start=lambda: None)))
    demo = tmp_path / 'valid.dem'
    demo.write_bytes(b'PBDEMS2\x00' + b'x' * 16)
    jobs = [client.post('/api/demo/from-path', json={'path': str(demo)}, headers={'X-NULLCS-KEY': 'test-only-key'}) for _ in range(2)]
    assert all(response.status_code == 200 for response in jobs)
    assert jobs[0].json()['demo_id'] != jobs[1].json()['demo_id']
    status = client.get('/api/demo/' + jobs[0].json()['demo_id'] + '/status', headers={'X-NULLCS-KEY': 'test-only-key'})
    assert status.status_code == 200
    assert status.json()['state'] == 'queued'
    assert status.json()['logs_tail'] == ''
