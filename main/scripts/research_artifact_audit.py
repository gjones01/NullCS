"""Inspect trusted local research artifacts and reproduce saved-score metrics.

Never use this on downloaded/untrusted pickle files. Fits ONLY disposable
cross-validation calibrators, not predictive models; never saves a model.
"""
from __future__ import annotations
import argparse
import importlib.metadata as metadata
import json
import sys
import time
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch
from sklearn.isotonic import IsotonicRegression
from sklearn.model_selection import GroupKFold
from xgboost import XGBClassifier

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.models.encounter_nn import load_trained_encounter_model
from research_validation import evaluate, metrics, sha256


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--processed', required=True, type=Path)
    ap.add_argument('--output', required=True, type=Path)
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    m, r = args.processed/'models', args.processed/'reports'
    names = ['encounter_nn_cs2cd.pt','encounter_nn_cs2cd_preproc.pkl','encounter_nn_cs2cd_features.json',
             'xgb_player_level_cs2cd.json','xgb_player_level_cs2cd_features.txt','xgb_player_level_cs2cd_calibration.pkl']
    result = dict(artifacts={n:sha256(m/n) for n in names}, versions={x:metadata.version(x) for x in ['torch','xgboost','scikit-learn','demoparser2','awpy','pandas','numpy']},
                  cuda=dict(build=torch.version.cuda, available=torch.cuda.is_available()))
    model, preproc, channels, device = load_trained_encounter_model(m/names[0], m/names[1], m/names[2])
    result['temporal'] = dict(architecture=str(model), channels=channels, parameters=sum(p.numel() for p in model.parameters()),
        seq_len=model._nullcs_seq_len, preproc_seq_len=preproc.seq_len,
        preproc_channels_match=channels == preproc.channel_cols, device=device)
    xgb = XGBClassifier(); xgb.load_model(m/names[3])
    features = (m/names[4]).read_text().splitlines()
    result['xgb'] = dict(feature_count=len(features), serialized_count=xgb.n_features_in_, config=json.loads(xgb.get_booster().save_config()))
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        cal = joblib.load(m/names[5])
    result['calibrator'] = dict(keys=list(cal), type=type(cal['model']).__name__,
        warning=[str(w.message) for w in caught], x=cal['model'].X_thresholds_.tolist(), y=cal['model'].y_thresholds_.tolist())
    path = r/'player_oof_predictions_cs2cd.parquet'
    df = pd.read_parquet(path)
    result['oof'] = dict(sha256=sha256(path), columns=df.columns.tolist())
    raw = 'proba_raw_oof' if 'proba_raw_oof' in df else 'proba_cheater_oof'
    f = df[['demo_id','attacker_steamid','map_name','y_true',raw]].rename(columns={'y_true':'label',raw:'score'})
    f['attacker_steamid'] = f.attacker_steamid.astype(str)
    f.to_csv(args.output/'historical_predictions.csv', index=False)
    result['historical_raw'] = evaluate(f)
    csv_path = r/'player_oof_predictions_cs2cd.csv'
    csv = pd.read_csv(csv_path, dtype={'attacker_steamid':str})
    result['historical_csv_raw'] = metrics(csv.y_true.to_numpy(),csv[raw].to_numpy())
    result['historical_csv_sha256'] = sha256(csv_path)
    original = df.copy(); original['attacker_steamid'] = original.attacker_steamid.astype(str)
    joined = original.merge(csv,on=['demo_id','attacker_steamid'],suffixes=('_parquet','_csv'),validate='one_to_one')
    result['historical_csv_parquet_differences'] = dict(joined_rows=len(joined),
        different_scores=int((~np.isclose(joined[raw+'_parquet'],joined[raw+'_csv'])).sum()))
    y, p = f.label.to_numpy(), f.score.to_numpy()
    result['saved_calibrator_on_current_oof_NOT_holdout'] = metrics(y, cal['model'].predict(p))
    # This isolates calibrator fit/evaluation reuse, NOT upstream stacking leakage.
    cross = np.zeros(len(f)); folds = np.zeros(len(f), dtype=int)
    overlap = []
    for i,(tr,te) in enumerate(GroupKFold(5).split(f,y,groups=f.demo_id),1):
        iso = IsotonicRegression(out_of_bounds='clip').fit(np.clip(p[tr],1e-6,1-1e-6),y[tr])
        cross[te] = iso.predict(np.clip(p[te],1e-6,1-1e-6)); folds[te] = i
        train_ids = set(f.iloc[tr].attacker_steamid)
        overlap.append(dict(fold=i, test_rows=len(te), shared_id_rows=int(f.iloc[te].attacker_steamid.isin(train_ids).sum()),
                            shared_ids=len(set(f.iloc[te].attacker_steamid)&train_ids),
                            shared_real_format_rows=int((f.iloc[te].attacker_steamid.str.fullmatch(r'[0-9]{17}') & f.iloc[te].attacker_steamid.isin(train_ids)).sum())))
    result['crossfit_calibration_diagnostic_NOT_full_stack_holdout'] = metrics(y,cross)
    result['player_id_overlap_reconstructed_folds'] = overlap
    result['label_conflicts_by_id'] = int((f.groupby('attacker_steamid').label.nunique()>1).sum())
    result['identity_warning'] = 'Most CS2CD IDs are anonymized Player_N slots, not linkable people. Shared IDs and conflicting labels on those slots do not prove player leakage or mislabeling.'
    result['demo_fold_integrity'] = {c: int((df.groupby('demo_id')[c].nunique()>1).sum()) for c in ['fold','fold_id'] if c in df}
    result['map_label_counts'] = f.groupby('map_name').label.agg(['count','sum','mean']).reset_index().to_dict('records')
    result['source_label_counts'] = f.assign(source=f.demo_id.str.extract(r'^(CS2CD_PROLEGIT|CS2CD_no_cheater_present|CS2CD_with_cheater_present)',expand=False).fillna('other')).groupby('source').label.agg(['count','sum','mean']).reset_index().to_dict('records')
    current = pd.read_parquet(args.processed/'player_features_cs2cd.parquet')
    nn = pd.read_parquet(args.processed/'encounter_nn_cs2cd_player_features.parquet')
    join = current.merge(nn,on=['demo_id','attacker_steamid'],suffixes=('_table','_nn'))
    result['nn_aggregate_vs_player_table'] = dict(matched_rows=len(join), differences={c:int((~np.isclose(join[c+'_table'],join[c+'_nn'],equal_nan=True)).sum()) for c in nn if c.startswith('enn_') and c+'_table' in join})
    enc_path = r/'encounter_nn_cs2cd_oof_encounters.parquet'
    enc = pd.read_parquet(enc_path, columns=['demo_id','attacker_steamid','victim_steamid','start_tick','end_tick','label','encounter_nn_score','visible_tick_count'])
    result['encounters'] = dict(rows=len(enc), demos=int(enc.demo_id.nunique()),
        saved_oof_metrics=metrics(enc.label.to_numpy(),enc.encounter_nn_score.to_numpy()),
        duration_quantiles=(enc.end_tick-enc.start_tick+1).quantile([0,.1,.5,.9,1]).to_dict(),
        candidate_rows_quantiles=enc.visible_tick_count.quantile([0,.1,.5,.9,1]).to_dict(),
        duplicate_window_keys=int(enc.duplicated(['demo_id','attacker_steamid','victim_steamid','start_tick','end_tick']).sum()))
    # Bound synthetic training-kernel benchmark; weights exist only in memory.
    torch.set_num_threads(4); torch.manual_seed(20261014)
    result['cpu_synthetic_kernel_benchmark'] = []
    for length in [32,64,96,128]:
        model.train(); x=torch.randn(128,len(channels),length); target=torch.zeros(128)
        opt=torch.optim.AdamW(model.parameters(),lr=.001)
        times=[]
        for step in range(6):
            start=time.perf_counter(); opt.zero_grad(set_to_none=True)
            loss=torch.nn.functional.binary_cross_entropy_with_logits(model(x).reshape(-1),target)
            loss.backward(); opt.step()
            if step: times.append(time.perf_counter()-start)
        result['cpu_synthetic_kernel_benchmark'].append(dict(samples=128,length=length,threads=4,
            median_step_seconds=float(np.median(times)),raw_tensor_gib_281792_rows=281792*35*length*4/1024**3))
    result['benchmark_limit'] = 'Synthetic CPU kernel only, 1 warmup + 5 timed steps. Not model training quality, real DataLoader throughput, GPU timing, or end-to-end duration.'
    (args.output/'audit.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6,5)); ax.plot([0,1],[0,1],':',color='gray')
    for key,label in [('historical_raw','Raw historical OOF'),('saved_calibrator_on_current_oof_NOT_holdout','Saved calibrator (not holdout)'),('crossfit_calibration_diagnostic_NOT_full_stack_holdout','Cross-fitted calibrator only')]:
        values=result[key]['supervised'] if key=='historical_raw' else result[key]
        curve=values['reliability']; ax.plot([b['prediction'] for b in curve],[b['observed'] for b in curve],'o-',label=label)
    ax.set(xlabel='Mean output in bin',ylabel='Observed research label frequency',title='Calibration diagnostic; not an independent test'); ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(args.output/'reliability.png',dpi=160); plt.close(fig)
    print(args.output)


if __name__ == '__main__':
    main()
