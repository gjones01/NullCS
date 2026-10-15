"""Export one completed fold for local canonical-inference validation, never promotion."""
import argparse
import json
from pathlib import Path
import shutil

import joblib
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
import torch

from research_validation import sha256


def selected_calibrator(fold_path, run, validation_dir):
    """Replay the development-only choice and bind it to this exact parent run."""
    report=json.loads((validation_dir/'summary.json').read_text())
    decision=next(d for d in report['decisions'] if d['fold']==run['fold']['fold'])
    if decision['parent_run_sha256']!=sha256(fold_path/'run.json'):
        raise ValueError('Calibration decision belongs to another model run')
    selection=json.loads((validation_dir/f"selection_{run['fold']['fold']}.json").read_text())
    cal=pd.read_parquet(fold_path/'calibration_predictions.parquet')
    # Group membership is supplied by main from the verified snapshot, not this report.
    return report,decision,selection,cal


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--fold',type=Path,required=True)
    ap.add_argument('--input',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--calibration-validation',type=Path,help='Verified development-only calibration comparison directory')
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
    method='isotonic'
    validation_sha=None
    dtype_delta=0.0
    if args.calibration_validation:
        from validate_calibration import select_method
        report,decision,selection,cal=selected_calibrator(args.fold,run,args.calibration_validation)
        if sha256(args.input/'split_manifest.json')!=input_manifest['snapshot_hashes']['split_manifest.json']:
            raise ValueError('Split snapshot changed')
        split=json.loads((args.input/'split_manifest.json').read_text())
        method,scores,memberships=select_method(cal,split['groups'])
        if method!='sigmoid' or decision['selected']!=method or scores!=decision['calibration_cv'] or memberships!=selection['cv_memberships']:
            raise ValueError('Development calibration selection could not be reproduced')
        calibrator=LogisticRegression(C=1,solver='lbfgs',max_iter=2000,random_state=20261015).fit(cal[['raw_score']].to_numpy(),cal.label)
        validation_sha=sha256(args.calibration_validation/'summary.json')
        # Check serialization and production input dtype against the recorded evaluation.
        expected=pd.read_parquet(args.calibration_validation/'predictions.parquet')
        expected=expected[expected.fold==run['fold']['fold']]
        original=pd.read_parquet(args.fold/'test_predictions.parquet')
        if list(zip(expected.demo_id,expected.attacker_steamid))!=list(zip(original.demo_id,original.attacker_steamid)):
            raise ValueError('Validation player rows differ from the original test')
        actual=calibrator.predict_proba(original.raw_score.to_numpy(dtype=float).reshape(-1,1))[:,1]
        native=calibrator.predict_proba(original[['raw_score']].to_numpy())[:,1]
        dtype_delta=float(np.max(np.abs(actual-expected.selected.to_numpy())))
        # Evaluation uses float32 XGBoost output; production scoring converts to float64.
        # Require exact replay at the original dtype and at most one float32 epsilon
        # at the production boundary. This does not change either scoring path.
        if not np.array_equal(native,expected.selected.to_numpy()) or dtype_delta>np.finfo(np.float32).eps:
            raise ValueError('Exported calibration differs from evaluated predictions')
    else:
        calibrator=IsotonicRegression(out_of_bounds='clip').fit(cal.raw_score.to_numpy(),cal.label)
        knots=json.loads((args.fold/'calibration.json').read_text())
        if not np.array_equal(calibrator.X_thresholds_,knots['x']) or not np.array_equal(calibrator.y_thresholds_,knots['y']):
            raise ValueError('Calibration replay differs from evaluated fold')
    joblib.dump(dict(method=method,model=calibrator),target/(stem+'_calibration.pkl'))
    provenance=dict(train_data_mode='cs2cd',pipeline_semantics='corrected-v2',experimental=True,
        parent_run_sha256=sha256(args.fold/'run.json'),max_demos=None,
        calibration_method=method,calibration_validation_sha256=validation_sha,
        calibration_float64_max_delta=dtype_delta,
        scope='Local validation bundle from one development fold; not a selected production model')
    for filename in [stem+'_training_manifest.json','encounter_nn_cs2cd_training_manifest.json']:
        (target/filename).write_text(json.dumps(provenance,indent=2),encoding='utf8')
    contract=dict(schema='nullcs.pipeline.v2',encounter_aggregation='aligned-v2',experimental=True,
        shrinkage_references=json.loads((args.fold/'shrinkage.json').read_text()),
        artifact_sha256={p.name:sha256(p) for p in target.iterdir() if p.is_file()})
    (target/(stem+'_pipeline_contract.json')).write_text(json.dumps(contract,indent=2),encoding='utf8')
    print(str(target))


if __name__=='__main__': main()
