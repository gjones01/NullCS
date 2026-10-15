"""Read-only lineage forensics; no predictive-model training or artifact replacement.

The only fit is a disposable isotonic replay to compare a saved calibrator with
its candidate input files. Trusted local artifacts only (joblib contains pickle).
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.models.encounter_nn import aggregate_encounter_scores, TemporalSequencePreprocessor, fit_temporal_preprocessor


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    return h.hexdigest()


def compare(left,right,columns):
    keys=['demo_id','attacker_steamid']
    left=left.copy();right=right.copy()
    for frame in [left,right]:
        for key in keys: frame[key]=frame[key].astype(str)
    joined=left.merge(right,on=keys,suffixes=('_left','_right'),validate='one_to_one')
    diffs={}
    for c in columns:
        a=pd.to_numeric(joined[c+'_left'],errors='raise').to_numpy(dtype=float)
        b=pd.to_numeric(joined[c+'_right'],errors='raise').to_numpy(dtype=float)
        finite=np.isfinite(a)&np.isfinite(b)
        diffs[c]=dict(different_rows=int((~np.isclose(a,b,rtol=1e-7,atol=1e-9,equal_nan=True)).sum()),
                      max_absolute_delta=float(np.abs(a[finite]-b[finite]).max()) if finite.any() else None)
    return dict(left_rows=len(left),right_rows=len(right),matched_rows=len(joined),columns=diffs)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--processed',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--check-temporal-cache',action='store_true',help='Recompute preprocessing statistics from the 1.18 GiB raw cache, without training a network')
    args=ap.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    m=args.processed/'models';r=args.processed/'reports'
    paths=[args.processed/'player_features_cs2cd.parquet',args.processed/'encounter_nn_cs2cd_player_features.parquet',
        r/'encounter_nn_cs2cd_oof_encounters.parquet',r/'encounter_nn_cs2cd_oof_players.parquet',
        r/'player_oof_predictions_cs2cd.parquet',r/'player_oof_predictions_cs2cd.csv']
    paths+= [m/n for n in ['encounter_nn_cs2cd.pt','encounter_nn_cs2cd_preproc.pkl','encounter_nn_cs2cd_features.json',
        'encounter_nn_cs2cd_training_manifest.json','xgb_player_level_cs2cd.json','xgb_player_level_cs2cd_features.txt',
        'xgb_player_level_cs2cd_training_manifest.json','xgb_player_level_cs2cd_calibration.pkl']]
    result={'files':{str(p.relative_to(args.processed)):{'sha256':sha(p),'size':p.stat().st_size,'mtime_unix':p.stat().st_mtime} for p in paths}}
    table=pd.read_parquet(paths[0]);current=pd.read_parquet(paths[1]);enc=pd.read_parquet(paths[2]);nn_report=pd.read_parquet(paths[3])
    old=pd.read_parquet(paths[4]);recent=pd.read_csv(paths[5],dtype={'attacker_steamid':str})
    features=(m/'xgb_player_level_cs2cd_features.txt').read_text().splitlines()
    neural=[c for c in features if c.startswith('enn_')]
    rebuilt=aggregate_encounter_scores(enc)
    result['reaggregate_current_encounters']=compare(rebuilt,current,neural)
    result['nn_report_vs_current']=compare(nn_report,current,neural)
    result['training_table_vs_current_nn']=compare(table,current,neural)
    result['training_table_vs_old_oof_features']=compare(table,old,features)
    result['training_table_vs_recent_oof_features']=compare(table,recent,features)
    result['old_vs_recent_oof']=compare(old,recent,['proba_raw_oof','y_true','fold_id',*features])
    calibrator=joblib.load(m/'xgb_player_level_cs2cd_calibration.pkl')['model']
    grid=np.linspace(0,1,10001)
    result['calibration_replay']={}
    for label,frame in [('parquet',old),('csv',recent)]:
        replay=IsotonicRegression(out_of_bounds='clip').fit(np.clip(frame.proba_raw_oof.to_numpy(),1e-6,1-1e-6),frame.y_true.to_numpy())
        result['calibration_replay'][label]=dict(
            x_thresholds_equal=np.array_equal(calibrator.X_thresholds_,replay.X_thresholds_),
            y_thresholds_equal=np.array_equal(calibrator.y_thresholds_,replay.y_thresholds_),
            saved_knots=len(calibrator.X_thresholds_),replayed_knots=len(replay.X_thresholds_),
            max_grid_prediction_delta=float(np.max(np.abs(calibrator.predict(grid)-replay.predict(grid)))))
    result['neural_distributions']={}
    for label,frame in [('historical_table',table),('current_temporal_oof',current)]:
        result['neural_distributions'][label]={c:frame[c].quantile([0,.1,.5,.9,1]).to_dict() for c in neural}
    if args.check_temporal_cache:
        cache=args.processed/'encounter_nn_cs2cd_temporal_seq32.npz'
        cache_manifest=m/'encounter_nn_cs2cd_temporal_seq32_manifest.json'
        manifest=json.loads(cache_manifest.read_text(encoding='utf8'))
        saved=TemporalSequencePreprocessor.load(m/'encounter_nn_cs2cd_preproc.pkl')
        with np.load(cache) as archive:
            raw=archive['temporal']
        computed=fit_temporal_preprocessor(raw,saved.channel_cols,saved.seq_len)
        result['cache_check']=dict(sha256=sha(cache),manifest_sha256=sha(cache_manifest),shape=list(raw.shape),
            channel_order_matches=manifest['channel_cols']==saved.channel_cols,
            demo_row_order_matches=manifest['demo_ids']==enc.demo_id.astype(str).tolist(),
            attacker_row_order_matches=manifest['attacker_steamids']==enc.attacker_steamid.astype(str).tolist(),
            statistics={field:dict(max_absolute_delta=max(abs(getattr(saved,field)[c]-getattr(computed,field)[c]) for c in saved.channel_cols),
                                  exact_match=getattr(saved,field)==getattr(computed,field)) for field in ['medians','means','scales']})
    result['source_hash']=sha(Path(__file__))
    result['limitations']=['Replaying OOF aggregation does not prove which checkpoint or preprocessing generated those encounter predictions.',
        'An exact calibrator replay establishes numerical consistency with a candidate input, not cryptographic historical training provenance.',
        'Timestamps are corroborative only. No original fold checkpoints or immutable per-run feature hashes are assumed.']
    (args.output/'lineage.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf8')
    print(args.output)


if __name__=='__main__': main()
