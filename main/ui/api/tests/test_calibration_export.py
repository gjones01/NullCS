import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression

sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'scripts'))
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from export_corrected_validation_bundle import selected_calibrator
from src.utils.scoring import maybe_calibrate


def test_export_rejects_selection_from_another_run(tmp_path):
    fold=tmp_path/'fold';validation=tmp_path/'validation'
    fold.mkdir();validation.mkdir()
    (fold/'run.json').write_text('{}')
    (validation/'summary.json').write_text(json.dumps(dict(decisions=[dict(fold=0,parent_run_sha256='wrong')])) )
    with pytest.raises(ValueError,match='another model run'):
        selected_calibrator(fold,dict(fold=dict(fold=0)),validation)


def test_serialized_sigmoid_matches_production_scoring(tmp_path):
    raw=np.array([.05,.1,.2,.4,.6,.8,.9,.95],dtype=np.float32)
    labels=[0,0,0,0,1,1,1,1]
    model=LogisticRegression(C=1,solver='lbfgs',max_iter=2000,random_state=20261015).fit(raw.reshape(-1,1),labels)
    path=tmp_path/'calibration.pkl'
    joblib.dump(dict(method='sigmoid',model=model),path)
    scores=maybe_calibrate(pd.Series(raw,index=range(10,18)),joblib.load(path))
    expected=model.predict_proba(raw.astype(float).reshape(-1,1))[:,1]
    np.testing.assert_array_equal(scores,expected)
    assert scores.index.tolist()==list(range(10,18))
    assert scores.between(0,1,inclusive='neither').all()
