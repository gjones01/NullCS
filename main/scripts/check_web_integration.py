"""Real HTTP end-to-end check through the website gateway (no model mocks).

Run against local/staging services with a demo you are authorized to upload.
Uses requests (already required by awpy). Does not need backend keys.
"""
from __future__ import annotations
import argparse
import json
import time
from pathlib import Path
from urllib.parse import urlsplit

import requests


class SiteSession(requests.Session):
    def __init__(self, origin, **headers):
        super().__init__()
        self.origin = origin
        self.headers.update(headers)

    def request(self, method, url, **kwargs):
        kwargs.setdefault('timeout', 30)
        return super().request(method, self.origin + url, **kwargs)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--site', required=True)
    p.add_argument('--demo', required=True, type=Path)
    p.add_argument('--repeat', type=int, choices=(1, 2), default=1)
    p.add_argument('--timeout', type=int, default=1800)
    p.add_argument('--json-out', type=Path)
    args = p.parse_args()
    origin = args.site.rstrip('/')
    assert urlsplit(origin).scheme in ('http', 'https')
    metadata = {'filename': args.demo.name, 'size': args.demo.stat().st_size}
    runs = []

    with SiteSession(origin, Origin=origin) as client:
        def get(path):
            response = client.get('/api/analysis' + path)
            response.raise_for_status()
            return response.json()

        capabilities = get('/capabilities')
        assert client.post('/api/analysis', json={**metadata, 'size': capabilities['max_upload_bytes'] + 1}).status_code == 413
        assert client.post('/api/analysis', json={**metadata, 'storage_key': '../private'}).status_code == 400
        assert client.post('/api/analysis', json=metadata, headers={'Origin': 'https://invalid.example'}).status_code == 403
        assert client.put('/api/analysis/anything/upload', data=b'not proxied').status_code == 405

        for index in range(args.repeat):
            start = time.monotonic()
            response = client.post('/api/analysis', json=metadata)
            response.raise_for_status()
            ticket = response.json()
            job = ticket['job_id']
            assert get(f'/{job}/status')['state'] == 'upload_pending'
            # The whole demo goes to the separately configured worker, not Next.js.
            assert urlsplit(ticket['upload_url']).netloc != urlsplit(origin).netloc
            with args.demo.open('rb') as source:
                upload = requests.put(ticket['upload_url'], data=source,
                                  headers={'Authorization': 'Bearer '+ticket['upload_token'], 'Content-Type': 'application/octet-stream', 'Content-Length': str(metadata['size'])}, timeout=args.timeout)
                upload.raise_for_status()
            upload_seconds = time.monotonic() - start
            print(f'[UPLOADED] {job}: {metadata["size"]} bytes in {upload_seconds:.2f}s', flush=True)
            deadline = time.monotonic() + args.timeout
            previous = None
            while True:
                status = get(f'/{job}/status')
                if status['stage'] != previous:
                    print(f'[STAGE] {status["stage"]}', flush=True)
                    previous = status['stage']
                if status['state'] == 'failed':
                    raise RuntimeError(status['error'])
                if status['state'] == 'results_ready':
                    break
                if time.monotonic() > deadline:
                    raise TimeoutError('Analysis did not finish')
                time.sleep(2)
            result = get(f'/{job}/results')
            assert result['players']
            assert all(player['explanation']['state'] == 'unavailable' for player in result['players'])
            assert [e['stage'] for e in status['events']] == ['upload_pending', 'uploading', 'queued', 'preparing', 'parsing', 'feature_processing', 'inference', 'scoring', 'results_ready']
            assert 'C:\\' not in json.dumps(result) and 'model_artifact_path' not in json.dumps(result)
            with SiteSession(origin) as stranger:
                assert stranger.get(f'/api/analysis/{job}/results').status_code == 401
                stranger.get('/api/analysis/capabilities').raise_for_status()
                assert stranger.get(f'/api/analysis/{job}/results').status_code == 404
                assert stranger.get(f'/api/analysis/{job}/status').status_code == 404
            sid = result['players'][0]['steamid']
            endpoint = f'/{job}/players/{sid}'
            client.post('/api/analysis'+endpoint+'/explain').raise_for_status()
            while True:
                explanation = get(endpoint+'/explanation')
                if explanation['status']['state'] == 'failed':
                    raise RuntimeError(explanation['status']['error'])
                if explanation['status']['state'] == 'ready':
                    break
                if time.monotonic() > deadline:
                    raise TimeoutError('Explanation did not finish')
                time.sleep(1)
            evidence = []
            for filename in explanation['report']['evidence_files']:
                table = get(endpoint+'/evidence/'+filename)
                evidence.append({'filename': filename, 'rows': len(table['rows'])})
            signature = [{k: player[k] for k in ('steamid', 'rank', 'model_score', 'calibrated_probability', 'risk', 'confidence')} for player in result['players']]
            runs.append({'job_id': job, 'upload_seconds': upload_seconds, 'runtime_seconds': status['runtime_seconds'],
                         'total_seconds': time.monotonic() - start, 'players': signature,
                         'model': result['model'], 'parser': result['demo']['parser_provenance'], 'evidence': evidence})
            print(f'[PASS] run {index+1}: {len(signature)} real ranked players; {len(evidence)} evidence tables', flush=True)
    deterministic = None if len(runs) == 1 else all(runs[0][key] == runs[1][key] for key in ('players', 'model', 'parser'))
    summary = {'demo': args.demo.name, 'size_bytes': metadata['size'], 'runs': runs, 'equal_ranked_outputs': deterministic}
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(summary, indent=2), encoding='utf8')
    print(f'[RESULT] repeated ranked outputs equal: {deterministic}', flush=True)
    return 0 if deterministic is not False else 1


if __name__ == '__main__':
    raise SystemExit(main())
