"""Snapshot local research inputs and group splits; never modify released artifacts."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
import time

import numpy as np
import pandas as pd

from research_validation import sha256


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data-root', required=True, type=Path)
    ap.add_argument('--output', required=True, type=Path)
    args = ap.parse_args()
    root = args.data_root.resolve()
    processed = root/'main/data/processed'
    os.environ['NULLCS_PROJECT_ROOT'] = str(root)
    os.environ['CLARITY_PROCESSED_DIR'] = str(processed)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from train_encounter_nn import _load_labeled_encounters, _load_temporal_cache
    from src.models.encounter_nn import temporal_channel_columns, build_temporal_sequences_for_demo
    from src.utils.research_splits import connected_groups, nested_plan

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    start = time.perf_counter()
    encounters = _load_labeled_encounters('cs2cd')
    channels = temporal_channel_columns()
    raw = _load_temporal_cache(encounters, 'cs2cd', 32, channels)
    if raw is None or raw.shape != (len(encounters), len(channels), 32):
        raise ValueError('Missing or misaligned raw temporal cache; regenerate explicitly')
    records, hashes, kills = [], {}, []
    for demo in sorted(encounters.demo_id.unique()):
        folder = processed/'demos'/demo
        meta = json.loads((folder/'meta.json').read_text(encoding='utf-8'))
        frame = pd.read_parquet(folder/'engagement_features.parquet')
        for label_frame in (frame, encounters[encounters.demo_id == demo]):
            if 'label' not in label_frame or not label_frame.label.isin([0,1]).all():
                raise ValueError(f'Missing or nonbinary source labels: {demo}')
        kills.append(frame)
        tokens = set()
        for part in (frame, encounters[encounters.demo_id == demo]):
            for column in ('attacker_steamid','victim_steamid'):
                for sid in part[column].dropna().astype(str).str.strip().unique():
                    if re.fullmatch(r'7656119\d{10}', sid):
                        tokens.add('player:'+sid)
        source_files = [folder/'meta.json',folder/'engagement_features.parquet',folder/'encounters.parquet']
        if demo.startswith('CS2CD_PROLEGIT_'):
            source = Path(meta['source_demo'])
            source_files.append(source)
            source_kind = 'pro_assumed_negative'
        else:
            source = root/'huggfacedata'/meta['split']/(str(meta['match_id'])+'.parquet')
            source_files.extend([source,source.with_suffix('.json')])
            source_kind = meta['split']
            tokens.add('dataset_match:'+meta['split']+':'+str(meta['match_id']))
        for path in source_files:
            hashes[str(path)] = sha256(path)
        tokens.add('source_bytes:'+hashes[str(source)])
        # Content fingerprints also join copied processed matches under new names.
        fingerprint_columns = [c for c in frame if c not in {'demo_id','label','label_source','dataset_source'}]
        canonical = frame[fingerprint_columns].sort_values(['kill_tick','attacker_steamid','victim_steamid'])
        import hashlib
        tokens.add('events:'+hashlib.sha256(pd.util.hash_pandas_object(canonical, index=False).values.tobytes()).hexdigest())
        records.append(dict(demo_id=demo,tokens=sorted(tokens),source=source_kind,
            identity_coverage='event_participants_only',encounters=int((encounters.demo_id==demo).sum())))
    groups = connected_groups(records)
    plan = nested_plan(groups)
    (output/'split_manifest.json').write_text(json.dumps(dict(groups=groups,records=records,folds=plan),indent=2),encoding='utf8')
    pd.concat(kills,ignore_index=True).to_parquet(output/'kills.parquet',index=False)
    encounters.to_parquet(output/'encounters.parquet',index=False)
    # Uncompressed, read-only memory mapping avoids repeated compressed cache decoding.
    np.save(output/'temporal.npy',raw,allow_pickle=False)
    checks = []
    samples = [next(d for d in encounters.demo_id.unique() if d.startswith(prefix)) for prefix in
        ('CS2CD_no_cheater_present_', 'CS2CD_with_cheater_present_', 'CS2CD_PROLEGIT_')]
    for demo in samples:
        index = np.flatnonzero(encounters.demo_id.to_numpy()==demo)
        rebuilt = build_temporal_sequences_for_demo(encounters.iloc[index].reset_index(drop=True),seq_len=32,channel_cols=channels)
        equal = bool(np.allclose(raw[index],rebuilt,rtol=1e-6,atol=1e-6,equal_nan=True))
        checks.append(dict(demo_id=demo,rows=len(index),matches_cache=equal))
        print(json.dumps(checks[-1]),flush=True)
    cache = processed/'encounter_nn_cs2cd_temporal_seq32.npz'
    hashes[str(cache)] = sha256(cache)
    hashes[str(processed/'models/encounter_nn_cs2cd_temporal_seq32_manifest.json')] = sha256(processed/'models/encounter_nn_cs2cd_temporal_seq32_manifest.json')
    feature_path = processed/'models/xgb_player_level_cs2cd_features.txt'
    features = feature_path.read_text().splitlines()
    (output/'features.json').write_text(json.dumps(features,indent=2),encoding='utf8')
    files = ['kills.parquet','encounters.parquet','temporal.npy','split_manifest.json','features.json']
    manifest = dict(schema='corrected-baseline-input-v1',input_hashes=hashes,
        snapshot_hashes={f:sha256(output/f) for f in files},channel_columns=channels,
        context=dict(pre=128,post=16,observations=32),cache_reconstruction_checks=checks,
        train_ready=all(c['matches_cache'] for c in checks),seconds=time.perf_counter()-start,
        limitations=['Source labels not independently adjudicated','Anonymous player identities cannot be joined across matches',
                      'Known-player grouping covers event participants; full roster verification remains required',
                      'Only three cache demos reconstructed; historical inputs retain incomplete original provenance',
                      'Historical dataset and hyperparameters have already informed model selection; internal evaluation only'])
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    if not manifest['train_ready']:
        raise RuntimeError('Raw cache reconstruction differs: inspect checks before fitting')
    print(json.dumps(dict(demos=len(groups),components=len(set(groups.values())),seconds=manifest['seconds'])),flush=True)


if __name__ == '__main__':
    main()
