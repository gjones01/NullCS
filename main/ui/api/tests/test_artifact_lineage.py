from pathlib import Path
from itertools import product

import numpy as np
import pandas as pd
import pytest

from main.scripts.check_artifact_lineage import compare


def test_lineage_comparison_aligns_identity_not_row_order():
    a=pd.DataFrame({'demo_id':['a','b'],'attacker_steamid':['1','2'],'feature':[.1,.2]})
    b=a.iloc[::-1].copy()
    assert compare(a,b,['feature'])['columns']['feature']['different_rows']==0
    b.loc[b.demo_id=='a','feature']=.8
    result=compare(a,b,['feature'])
    assert result['matched_rows']==2
    assert result['columns']['feature']['different_rows']==1
    assert result['columns']['feature']['max_absolute_delta']==pytest.approx(.7)


def test_lineage_comparison_rejects_duplicate_join_keys():
    a=pd.DataFrame({'demo_id':['a','a'],'attacker_steamid':['1','1'],'feature':[.1,.2]})
    with pytest.raises(pd.errors.MergeError): compare(a,a,['feature'])


def test_missingness_is_part_of_lineage_comparison():
    a=pd.DataFrame({'demo_id':['a','b'],'attacker_steamid':['1','2'],'feature':[np.nan,.2]})
    assert compare(a,a,['feature'])['columns']['feature']['different_rows']==0
    b=a.fillna(0)
    assert compare(a,b,['feature'])['columns']['feature']['different_rows']==1


def test_experiment_matrix_is_independent_and_only_baseline_is_authorized():
    root=Path(__file__).resolve().parents[4]
    df=pd.read_csv(root/'research/encounter_context_matrix.csv')
    observed=set(zip(df.span_ticks,df.post_ticks,df.cnn_observations))
    assert observed==set(product([96,144],[0,16,32,48],[32,64,96]))
    assert len(df)==len(observed)==24
    assert (df.pre_ticks+df.post_ticks==df.span_ticks).all()
    assert (df.max_inclusive_positions==df.span_ticks+1).all()
    assert df.missing_event_sentinel_ticks.eq(256).all()
    assert df.loc[df.approved_for_training, 'configuration'].tolist() == ['D144_Q16_N32']
