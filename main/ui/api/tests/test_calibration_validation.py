import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]/'scripts'))
from validate_calibration import select_method, fit_predict, threshold_counts


def example():
    return pd.DataFrame(dict(demo_id=np.repeat(['a','b','c','d','e','f'], 2),
        attacker_steamid=['1','2']*6, label=[0,1]*6, raw_score=[.2,.8]*6))


def test_selection_groups_and_repeatability():
    data=example(); groups={d:d for d in data.demo_id.unique()}
    first=select_method(data,groups)
    assert first==select_method(data,groups)
    for split in first[2]:
        assert not set(split['fit_demos']) & set(split['heldout_demos'])
    assert np.array_equal(fit_predict('raw',data,data),data.raw_score)


def test_unknown_groups_and_invalid_scores_rejected():
    data=example()
    with pytest.raises(ValueError,match='known calibration groups'):
        select_method(data,{'a':'a'})
    data.loc[0,'raw_score']=np.nan
    with pytest.raises(ValueError,match='Missing'):
        select_method(data,{d:d for d in data.demo_id.unique()})


def test_predict_does_not_consume_test_labels():
    fit=example(); test=fit.copy()
    for method in ['raw','sigmoid','isotonic']:
        expected=fit_predict(method,fit,test)
        test['label']=1-test.label
        np.testing.assert_array_equal(expected,fit_predict(method,fit,test))


def test_threshold_counts_use_negative_match_denominator():
    frame=pd.DataFrame(dict(demo_id=['a','a','b','b'], label=[0,0,0,1], score=[.9,.1,.7,.8]))
    result=threshold_counts(frame,'score')[0]
    assert result['negative_players']==3
    assert result['flagged_negative_players']==2
    assert result['scored_negative_matches']==1
    assert result['flagged_scored_negative_matches']==1
    # An excluded positive player must not turn a positive match into a negative one.
    result=threshold_counts(frame,'score',pd.Series({'a':1,'b':1}))[0]
    assert result['scored_negative_matches']==0
