"""Fixed-configuration nested stacking experiment; never a production model writer.

Four epochs are fixed before evaluation (the released manifest's count), not
selected against outer holdouts. Source labels support internal evaluation only.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import random
import sys
import time

import numpy as np
import pandas as pd
import torch
from sklearn.isotonic import IsotonicRegression
from xgboost import XGBClassifier

from research_validation import sha256, metrics


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input',required=True,type=Path)
    ap.add_argument('--output',required=True,type=Path)
    ap.add_argument('--fold',required=True,type=int,choices=range(5))
    ap.add_argument('--device',choices=['cpu','cuda'],default='cpu')
    ap.add_argument('--threads',type=int,default=4)
    ap.add_argument('--batch-size',type=int,default=2048)
    ap.add_argument('--preflight-only',action='store_true')
    args=ap.parse_args()
    if args.threads<1 or args.batch_size<1:
        ap.error('threads and batch size must be positive')
    if args.device=='cuda' and not torch.cuda.is_available():
        raise RuntimeError('CUDA requested but unavailable; no silent CPU fallback')
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    from train_encounter_nn import _fit_full_model, _augment_scored_encounters
    from src.models.encounter_nn import build_model, predict_probabilities, aggregate_encounter_scores
    from src.features.aggregate_player_features import aggregate_kill_and_encounter_frames
    from src.utils.research_splits import assert_disjoint_groups
    from src.utils.scoring import apply_rt_low_evidence_downweight

    source=args.input.resolve()
    manifest=json.loads((source/'manifest.json').read_text())
    if manifest['schema']!='corrected-baseline-input-v1' or not manifest['train_ready']:
        raise ValueError('Input snapshot not cleared for an internal experiment')
    for name,digest in manifest['snapshot_hashes'].items():
        if sha256(source/name)!=digest:
            raise ValueError(f'Input changed: {name}')
    split=json.loads((source/'split_manifest.json').read_text())
    fold=split['folds'][args.fold]
    assert_disjoint_groups({k:fold[k] for k in ('development','calibration','test')},split['groups'])
    channels=manifest['channel_columns']
    features=json.loads((source/'features.json').read_text())
    if len(features)!=449 or len(set(features))!=449:
        raise ValueError('Expected unique 449-feature contract')
    encounters=pd.read_parquet(source/'encounters.parquet')
    kills=pd.read_parquet(source/'kills.parquet')
    raw=np.load(source/'temporal.npy',mmap_mode='r',allow_pickle=False)
    if raw.shape!=(len(encounters),len(channels),32):
        raise ValueError('Temporal tensor shape mismatch')
    torch.set_num_threads(args.threads)
    torch.use_deterministic_algorithms(True)
    if args.device=='cuda':
        os.environ['CUBLAS_WORKSPACE_CONFIG']=':4096:8'
        torch.backends.cudnn.benchmark=False
    output=args.output.resolve()
    output.mkdir(parents=True,exist_ok=False)
    begun=time.perf_counter()
    config=dict(model_type='temporal_cnn',seq_len=32,lr=.001,weight_decay=.0001,
        batch_size=args.batch_size,device=args.device,temporal_workers=1)
    fit_args=argparse.Namespace(**config)
    fit_records=[]
    # Fail on data/schema issues before spending time fitting neural networks.
    dev_kills=kills[kills.demo_id.isin(fold['development'])]
    dev_enc=encounters[encounters.demo_id.isin(fold['development'])]
    preliminary=aggregate_kill_and_encounter_frames(dev_kills,dev_enc)
    eligible=set(preliminary.demo_id.astype(str))
    handcrafted=aggregate_kill_and_encounter_frames(kills,encounters,shrinkage_fit_demo_ids=eligible)
    references=handcrafted.attrs['shrinkage_references']
    known_encounters=encounters[['demo_id','attacker_steamid']].drop_duplicates()
    coverage=handcrafted[['demo_id','attacker_steamid']].merge(known_encounters,how='left',indicator=True)
    if (coverage['_merge']!='both').any():
        raise ValueError('Eligible players without encounters; resolve coverage policy before training')
    handcrafted_features=[f for f in features if not f.startswith('enn_')]
    if set(handcrafted_features)-set(handcrafted):
        raise ValueError('Handcrafted feature contract incomplete')
    if args.preflight_only:
        report=dict(status='preflight_passed',player_rows=len(handcrafted),
            rows_after_n_players_filter=int((handcrafted.n_players>=8).sum()),
            shrinkage_references=references,seconds=time.perf_counter()-begun)
        (output/'preflight.json').write_text(json.dumps(report,indent=2),encoding='utf8')
        print(json.dumps(report),flush=True)
        return

    def indices(demos):
        return np.flatnonzero(encounters.demo_id.isin(demos).to_numpy())

    def fit_and_predict(name,fit_demos,predict_demos,seed):
        assert_disjoint_groups(dict(fit=fit_demos,predict=predict_demos),split['groups'])
        random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
        fit_idx, pred_idx=indices(fit_demos),indices(predict_demos)
        if set(encounters.iloc[fit_idx].label.unique())!={0,1}:
            raise ValueError('CNN training partition needs both classes')
        start=time.perf_counter()
        state,preproc=_fit_full_model(encounters.iloc[fit_idx],channels,4,fit_args,raw_x=raw[fit_idx])
        target=output/name
        target.mkdir()
        torch.save(state,target/'weights.pt')
        preproc.save(target/'preproc.pkl')
        model=build_model(len(channels),model_type='temporal_cnn').to(args.device)
        model.load_state_dict(state)
        # Transform only bounded prediction batches; raw tensor stays memory mapped.
        scores=[]
        for start_idx in range(0,len(pred_idx),4096):
            batch=raw[pred_idx[start_idx:start_idx+4096]]
            scores.append(predict_probabilities(model,preproc.transform_array(batch),batch_size=args.batch_size,device=args.device))
        scored=encounters.iloc[pred_idx].copy()
        scored['encounter_nn_score']=np.concatenate(scores)
        parent=sha256(target/'weights.pt')
        scored['producing_checkpoint_sha256']=parent
        scored.to_parquet(target/'predictions.parquet',index=False)
        record=dict(name=name,seed=seed,epochs=4,fit_demos=fit_demos,predict_demos=predict_demos,
            checkpoint_sha256=parent,preprocessor_sha256=sha256(target/'preproc.pkl'),seconds=time.perf_counter()-start)
        (target/'manifest.json').write_text(json.dumps(record,indent=2),encoding='utf8')
        fit_records.append(record)
        print(json.dumps(dict(fit=name,seconds=record['seconds'])),flush=True)
        del model,state
        return aggregate_encounter_scores(_augment_scored_encounters(scored),semantics='aligned-v2')

    run_manifest=dict(status='running',input_manifest_sha256=sha256(source/'manifest.json'),fold=fold,
        cnn=config,epochs=4,aggregation='aligned-v2',shrinkage='train-reference-v2',seed=20261014,
        limitations=manifest['limitations'],python=sys.version,torch=torch.__version__,
        code_hashes={str(p.relative_to(Path(__file__).resolve().parents[1])):sha256(p)
            for base in ('src','scripts') for p in (Path(__file__).resolve().parents[1]/base).rglob('*.py')})
    def save_status():
        (output/'run.json').write_text(json.dumps(run_manifest,indent=2),encoding='utf8')
    save_status()
    try:
        neural=[]
        for index,inner in enumerate(fold['cnn_crossfit']):
            assert_disjoint_groups(dict(**inner,calibration=fold['calibration'],test=fold['test']),split['groups'])
            neural.append(fit_and_predict(f'cnn_oof_{index}',inner['fit'],inner['heldout'],20261014+args.fold*10+index))
        neural.append(fit_and_predict('cnn_final',fold['development'],fold['calibration']+fold['test'],20261014+args.fold*10+4))
        table=handcrafted.merge(pd.concat(neural,ignore_index=True),on=['demo_id','attacker_steamid'],how='left',validate='one_to_one')
        if table['enn_score_mean'].isna().any():
            raise ValueError('Eligible players missing CNN predictions; do not silently zero-fill')
        if set(features)-set(table):
            raise ValueError(f'Missing contract fields: {sorted(set(features)-set(table))}')
        table=table[table.n_players>=8].copy()
        train=table[table.demo_id.isin(fold['development'])]
        calibration=table[table.demo_id.isin(fold['calibration'])]
        test=table[table.demo_id.isin(fold['test'])]
        for name,part in [('development',train),('calibration',calibration),('test',test)]:
            if set(part.label.unique())!={0,1}:
                raise ValueError(f'{name} needs both classes after eligibility')
        params=dict(n_estimators=800,max_depth=3,learning_rate=.03,min_child_weight=8,
            reg_lambda=5.,reg_alpha=0.,gamma=0.,subsample=1.,colsample_bytree=.8,
            objective='binary:logistic',eval_metric='logloss',tree_method='hist',n_jobs=args.threads,
            random_state=20261014,scale_pos_weight=float((train.label==0).sum()/(train.label==1).sum()))
        model=XGBClassifier(**params)
        model.fit(train[features].fillna(0.),train.label)
        model.save_model(output/'xgb.json')
        c_raw=model.predict_proba(calibration[features].fillna(0.))[:,1]
        calibrator=IsotonicRegression(out_of_bounds='clip').fit(c_raw,calibration.label)
        result=test[['demo_id','attacker_steamid','map_name','label','rt_n']].copy()
        result['raw_score']=model.predict_proba(test[features].fillna(0.))[:,1]
        result['calibrated_probability']=calibrator.predict(result.raw_score)
        result['review_score']=apply_rt_low_evidence_downweight(result.calibrated_probability,result.rt_n)
        result['component']=result.demo_id.map(split['groups'])
        result.to_parquet(output/'test_predictions.parquet',index=False)
        calibration=calibration[['demo_id','attacker_steamid','label']].copy()
        calibration['raw_score']=c_raw
        calibration.to_parquet(output/'calibration_predictions.parquet',index=False)
        (output/'calibration.json').write_text(json.dumps(dict(x=calibrator.X_thresholds_.tolist(),y=calibrator.y_thresholds_.tolist())),encoding='utf8')
        (output/'shrinkage.json').write_text(json.dumps(references,indent=2),encoding='utf8')
        run_manifest.update(status='complete',seconds=time.perf_counter()-begun,cnn_fits=fit_records,
            xgb_parameters=params,rows=dict(development=len(train),calibration=len(calibration),test=len(result)),
            metrics={column:metrics(result.label,result[column]) for column in ('raw_score','calibrated_probability','review_score')},
            artifacts={p.name:sha256(p) for p in output.iterdir() if p.is_file() and p.name!='run.json'})
    except BaseException as exc:
        run_manifest.update(status='failed',error_type=type(exc).__name__,error=str(exc),cnn_fits=fit_records,seconds=time.perf_counter()-begun)
        raise
    finally:
        save_status()


if __name__=='__main__':
    main()
