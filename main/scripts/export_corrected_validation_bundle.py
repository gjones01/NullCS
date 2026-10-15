"""Export one completed fold for local canonical-inference validation, never promotion."""
import argparse
import json
from pathlib import Path
import shutil

import joblib
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
import torch

from research_validation import sha256


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--fold',type=Path,required=True)
    ap.add_argument('--input',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    run=json.loads((args.fold/'run.json').read_text())
    if run['status']!='complete' or sha256(args.input/'manifest.json')!=run['input_manifest_sha256']:
        raise ValueError('Completed fold and its original input manifest required')
    for name,digest in run['artifacts'].items():
        if sha256(args.fold/name)!=digest: raise ValueError(f'Artifact changed: {name}')
    cnn=next(f for f in run['cnn_fits'] if f['name']=='cnn_final')
    source=args.fold/'cnn_final'
    for name,key in [('weights.pt','checkpoint_sha256'),('preproc.pkl','preprocessor_sha256')]:
        if sha256(source/name)!=cnn[key]: raise ValueError('CNN artifact changed')
    input_manifest=json.loads((args.input/'manifest.json').read_text())
    if sha256(args.input/'features.json')!=input_manifest['snapshot_hashes']['features.json']:
        raise ValueError('Feature contract changed')
    target=args.output.resolve()
    target.mkdir(parents=True,exist_ok=False)
    stem='xgb_player_level_cs2cd'
    shutil.copy2(args.fold/'xgb.json',target/(stem+'.json'))
    features=json.loads((args.input/'features.json').read_text())
    (target/(stem+'_features.txt')).write_text('\n'.join(features)+'\n',encoding='utf8')
    torch.save(dict(state_dict=torch.load(source/'weights.pt',map_location='cpu',weights_only=True),input_dim=35,
        hidden_dims=(256,128,64),dropout=.15,model_type='temporal_cnn',seq_len=32,train_data_mode='cs2cd'),target/'encounter_nn_cs2cd.pt')
    shutil.copy2(source/'preproc.pkl',target/'encounter_nn_cs2cd_preproc.pkl')
    channels=input_manifest['channel_columns']
    (target/'encounter_nn_cs2cd_features.json').write_text(json.dumps(dict(feature_columns=channels,count=len(channels))),encoding='utf8')
    cal=pd.read_parquet(args.fold/'calibration_predictions.parquet')
    calibrator=IsotonicRegression(out_of_bounds='clip').fit(cal.raw_score.to_numpy(),cal.label)
    knots=json.loads((args.fold/'calibration.json').read_text())
    if not np.array_equal(calibrator.X_thresholds_,knots['x']) or not np.array_equal(calibrator.y_thresholds_,knots['y']):
        raise ValueError('Calibration replay differs from evaluated fold')
    joblib.dump(dict(method='isotonic',model=calibrator),target/(stem+'_calibration.pkl'))
    provenance=dict(train_data_mode='cs2cd',pipeline_semantics='corrected-v2',experimental=True,
        parent_run_sha256=sha256(args.fold/'run.json'),max_demos=None,
        scope='Local validation bundle from one development fold; not a selected production model')
    for filename in [stem+'_training_manifest.json','encounter_nn_cs2cd_training_manifest.json']:
        (target/filename).write_text(json.dumps(provenance,indent=2),encoding='utf8')
    contract=dict(schema='nullcs.pipeline.v2',encounter_aggregation='aligned-v2',experimental=True,
        shrinkage_references=json.loads((args.fold/'shrinkage.json').read_text()),
        artifact_sha256={p.name:sha256(p) for p in target.iterdir() if p.is_file()})
    (target/(stem+'_pipeline_contract.json')).write_text(json.dumps(contract,indent=2),encoding='utf8')
    print(str(target))


if __name__=='__main__': main()
