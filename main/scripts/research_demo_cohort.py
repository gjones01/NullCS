"""Run local demos through the canonical pipeline, isolated from production.

Manifest JSON is a list of {demo_path, cohort, labels?}; labels is an optional
SteamID -> 0/1 mapping backed by independent review. No labels means no accuracy.
Model directory must be a trusted complete release bundle. Nothing is uploaded.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import pandas as pd
from research_validation import evaluate, sha256


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--manifest',required=True,type=Path)
    ap.add_argument('--models',required=True,type=Path)
    ap.add_argument('--output',required=True,type=Path)
    ap.add_argument('--timeout',type=int,default=1800)
    args=ap.parse_args()
    entries=json.loads(args.manifest.read_text(encoding='utf-8-sig'))
    if not isinstance(entries,list) or not entries or args.timeout <= 0:
        ap.error('Nonempty manifest list and positive timeout required')
    for entry in entries:
        if not isinstance(entry,dict) or 'demo_path' not in entry or 'cohort' not in entry:
            ap.error('Each entry needs demo_path and cohort')
        if not isinstance(entry['demo_path'],str) or not isinstance(entry['cohort'],str) or not entry['cohort'].strip() or not isinstance(entry.get('labels',{}),dict):
            ap.error('demo_path/cohort must be strings and labels a mapping')
        if any(v not in (0,1) for v in entry.get('labels',{}).values()):
            ap.error('Supplied labels must be 0/1')
    args.output=args.output.resolve()
    args.output.mkdir(parents=True,exist_ok=False)
    models=args.output/'processed'/'models'
    shutil.copytree(args.models,models)
    artifact_hashes={p.name:sha256(p) for p in models.iterdir() if p.is_file()}
    runs, predictions=[],[]
    seen_demos=set()
    env=os.environ.copy()
    env.update(NULLCS_PROJECT_ROOT=str(Path(__file__).resolve().parents[2]),
               CLARITY_PROCESSED_DIR=str(args.output/'processed'),NULLCS_UPLOAD_DIR=str(args.output/'uploads'))
    for index,entry in enumerate(entries):
        job=f'TEST_RESEARCH_{index:05d}'
        source=Path(entry['demo_path']); start=time.perf_counter()
        record=dict(job_id=job,cohort=entry['cohort'],status='failed')
        try:
            if source.suffix.lower()!='.dem': raise ValueError('Expected .dem')
            record['demo_sha256']=sha256(source)
            if record['demo_sha256'] in seen_demos:
                raise ValueError('Duplicate demo bytes; compare repeats separately rather than counting them as independent matches')
            seen_demos.add(record['demo_sha256'])
            with (args.output/f'{job}.log').open('w',encoding='utf8') as log:
                run=subprocess.run([sys.executable,str(Path(__file__).with_name('run_infer_pipeline.py')),
                    '--dem_path',str(source.resolve()),'--demo_id',job,'--out_dir',str(args.output/'processed'),
                    '--model-artifact','xgb_player_level_cs2cd.json'],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=args.timeout)
            record['exit_code']=run.returncode
            if run.returncode: raise RuntimeError('Pipeline failed; inspect local log')
            report=args.output/'processed'/'reports'/job
            df=pd.read_csv(report/'ranked_players_infer.csv',dtype={'attacker_steamid':str})
            coverage=json.loads((report/'player_coverage.json').read_text(encoding='utf8'))
            record.update(status='completed',coverage=coverage['counts'])
            for _,row in df.iterrows():
                predictions.append(dict(demo_id=job,attacker_steamid=row.attacker_steamid,map_name=row.map_name,
                    cohort=entry['cohort'],score=float(row.proba_cheater_infer),label=entry.get('labels',{}).get(row.attacker_steamid)))
        except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired) as exc:
            record['error']=str(exc)
        record['seconds']=time.perf_counter()-start; runs.append(record)
        (args.output/'runs.json').write_text(json.dumps(runs,indent=2),encoding='utf8')
    frame=pd.DataFrame(predictions,columns=['demo_id','attacker_steamid','map_name','cohort','score','label'])
    frame.to_csv(args.output/'predictions.csv',index=False)
    summary=evaluate(frame) if len(frame) else dict(supervised=None,rows=0)
    summary.update(attempted=len(runs),failed=sum(r['status']!='completed' for r in runs),
        manifest_sha256=sha256(args.manifest),artifact_hashes=artifact_hashes,
        source_hashes={str(p.relative_to(Path(__file__).resolve().parents[1])):sha256(p)
                       for folder in ['src','scripts'] for p in (Path(__file__).resolve().parents[1]/folder).rglob('*.py')},
        note='Failure rate includes intake/parser/feature/model failures; see per-run logs. No accuracy for unlabeled cohorts.')
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False),encoding='utf8')
    print(args.output)


if __name__=='__main__': main()
