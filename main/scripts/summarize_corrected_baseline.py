"""Combine exactly five disjoint outer folds; report internal evidence, not release accuracy."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from research_validation import metrics, sha256


def summarize(paths, input_dir):
    frames=[]; runs=[]; seen=set(); parent=None; protocol=None
    for path in paths:
        run=json.loads((path/'run.json').read_text())
        if run['status']!='complete': raise ValueError('Incomplete fold')
        if parent is None: parent=run['input_manifest_sha256']
        if parent!=run['input_manifest_sha256']: raise ValueError('Different input snapshots')
        core_code={name:digest for name,digest in run['code_hashes'].items()
            if name.replace('\\','/').startswith('src/') or name.replace('\\','/') in
            {'scripts/train_corrected_baseline.py','scripts/train_encounter_nn.py'}}
        current_protocol=dict(cnn=run['cnn'],epochs=run['epochs'],aggregation=run['aggregation'],
            shrinkage=run['shrinkage'],code=core_code)
        if protocol is None: protocol=current_protocol
        if current_protocol!=protocol: raise ValueError('Training protocol or core source changed between folds')
        fold=run['fold']['fold']
        if fold in seen: raise ValueError('Duplicate fold')
        seen.add(fold)
        for filename,digest in run['artifacts'].items():
            if sha256(path/filename)!=digest: raise ValueError(f'Changed artifact: {filename}')
        frame=pd.read_parquet(path/'test_predictions.parquet')
        if len(run['cnn_fits'])!=5: raise ValueError('Expected four cross-fit CNNs and one final CNN')
        for fit in run['cnn_fits']:
            target=path/fit['name']
            if sha256(target/'weights.pt')!=fit['checkpoint_sha256'] or sha256(target/'preproc.pkl')!=fit['preprocessor_sha256']:
                raise ValueError('CNN or preprocessing artifact changed')
            if set(fit['fit_demos']) & (set(run['fold']['test'])|set(run['fold']['calibration'])):
                raise ValueError('Held-out labels reached CNN fitting')
            if set(fit['fit_demos']) & set(fit['predict_demos']):
                raise ValueError('In-sample CNN feature generation')
        frame['fold']=fold
        if not set(frame.demo_id).issubset(run['fold']['test']): raise ValueError('Predictions outside test split')
        frames.append(frame); runs.append(run)
    if seen!=set(range(5)): raise ValueError('Five completed outer folds required')
    frame=pd.concat(frames,ignore_index=True)
    if sha256(input_dir/'manifest.json')!=parent: raise ValueError('Wrong input manifest')
    snapshot=json.loads((input_dir/'manifest.json').read_text())
    for filename in ['kills.parquet','encounters.parquet']:
        if sha256(input_dir/filename)!=snapshot['snapshot_hashes'][filename]: raise ValueError('Changed label snapshot')
    # Match-level denominators include labeled players excluded by model eligibility.
    labels=pd.concat([pd.read_parquet(input_dir/name,columns=['demo_id','attacker_steamid','label'])
        for name in ['kills.parquet','encounters.parquet']],ignore_index=True).drop_duplicates()
    if labels.groupby(['demo_id','attacker_steamid']).label.nunique().gt(1).any():
        raise ValueError('Conflicting player-match source labels')
    match_labels=labels.groupby('demo_id').label.max()
    positive_matches=match_labels.eq(1)
    if frame.duplicated(['demo_id','attacker_steamid']).any(): raise ValueError('Repeated evaluated player-match')
    if (frame.groupby('component').fold.nunique()>1).any(): raise ValueError('Component crosses outer folds')
    results={column:metrics(frame.label,frame[column]) for column in ['raw_score','calibrated_probability','review_score']}
    for column in results:
        thresholds=[]
        for threshold in [.2,.5,.8]:
            flag=frame[column]>=threshold
            negative=frame.label==0
            negative_matches=match_labels.eq(0)
            flagged_matches=frame.assign(flag=flag).groupby('demo_id').flag.max().reindex(match_labels.index,fill_value=False)
            thresholds.append(dict(threshold=threshold,negative_players=int(negative.sum()),
                flagged_negative_players=int((negative&flag).sum()),
                negative_matches=int(negative_matches.sum()),
                flagged_negative_matches=int((negative_matches&flagged_matches).sum())))
        results[column]['thresholds']=thresholds
    ranking=[]
    for k in [1,3,5]:
        selected=frame.sort_values(['review_score','attacker_steamid'],ascending=[False,True],kind='stable').groupby('demo_id').head(k)
        retrieved=selected.groupby('demo_id').label.max().eq(1).reindex(match_labels.index,fill_value=False)
        lower=upper=0
        for demo,part in frame.groupby('demo_id'):
            if not positive_matches.loc[demo]: continue
            cutoff=part.review_score.nlargest(min(k,len(part))).iloc[-1]
            above=part[part.review_score>cutoff]
            tied=part[part.review_score==cutoff]
            slots=min(k,len(part))-len(above)
            lower+=int(above.label.eq(1).any() or slots>tied.label.eq(0).sum())
            upper+=int(above.label.eq(1).any() or tied.label.eq(1).any())
        ranking.append(dict(k=k,positive_matches=int(positive_matches.sum()),
            positive_matches_retrieved=int((positive_matches&retrieved).sum()),
            tied_score_retrieval_lower=lower,tied_score_retrieval_upper=upper,
            tie_policy='Ascending player ID for deterministic reporting; tie bounds also shown',
            selected_players=len(selected),selected_positive_players=int(selected.label.sum())))
    source=np.where(frame.demo_id.str.startswith('CS2CD_PROLEGIT_'),'pro_assumed_negative',
        np.where(frame.demo_id.str.startswith('CS2CD_no_cheater_present_'),'negative_source','positive_source'))
    frame['source']=source
    slices={name:metrics(part.label,part.raw_score) for name,part in frame.groupby('source')}
    rng=np.random.default_rng(20261014)
    components=[g for _,g in frame.groupby('component',sort=True)]
    bootstrap=[]
    for _ in range(200):
        sample=pd.concat([components[i] for i in rng.integers(0,len(components),len(components))],ignore_index=True)
        bootstrap.append(metrics(sample.label,sample.raw_score))
    intervals={name:np.quantile([b[name] for b in bootstrap if b[name] is not None],[.025,.975]).tolist()
        for name in ['average_precision','roc_auc','brier']}
    return dict(scope='Corrected internal historical-data evaluation; not independent external or released-model validation',
        protocol=protocol,
        rows=len(frame),demos=int(frame.demo_id.nunique()),components=len(components),metrics=results,
        coverage=dict(source_matches=len(match_labels),evaluated_matches=int(frame.demo_id.nunique()),
            source_player_match_rows=int(labels[['demo_id','attacker_steamid']].drop_duplicates().shape[0]),
            scored_player_match_rows=len(frame),note='Historical observed event participants; not a verified full roster. Unscored matches are abstentions, not correct negatives.'),
        review_retrieval=ranking,source_slices=slices,raw_score_component_bootstrap_95=intervals,
        bootstrap_replicates=200,seed=20261014,limitations=runs[0]['limitations'],
        fold_seconds=[r['seconds'] for r in sorted(runs,key=lambda r:r['fold']['fold'])],
        run_hashes={str(p):sha256(p/'run.json') for p in paths})


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--folds',nargs=5,type=Path,required=True)
    ap.add_argument('--input',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    if args.output.exists(): raise FileExistsError(args.output)
    result=summarize(args.folds,args.input)
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf8')
    print(json.dumps(dict(rows=result['rows'],demos=result['demos'],scope=result['scope'])))


if __name__=='__main__': main()
