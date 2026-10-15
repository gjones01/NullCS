from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from main.scripts.research_validation import evaluate, reliability, validate
from main.src.utils.player_coverage import collect_coverage, finish_coverage


def test_coverage_is_not_a_ten_player_assumption():
    match = SimpleNamespace(ticks_df=pd.DataFrame({'steamid':['a','b','c'], 'name':['A','B','C']}),
        kills=pd.DataFrame({'attacker_steamid':['a','b'], 'victim_steamid':['c','d']}),
        shots=pd.DataFrame(), damages=pd.DataFrame())
    kills = pd.DataFrame({'attacker_steamid':['a']*5+['b']*7, 'rt_ticks':[1]*5+[None]*7})
    coverage = collect_coverage(match,kills,pd.DataFrame(),5)
    finish_coverage(coverage,['a'],['a'])
    assert coverage['counts'] == dict(detected=4,with_tick_telemetry=3,with_encounters=0,eligible=1,scored=1,not_scored=3)
    people = {p['steamid']:p for p in coverage['participants']}
    assert people['b']['valid_rt_kills']==0
    assert people['b']['status']=='not_scored'
    assert 'at least 5' in people['b']['reason']
    assert 'No tick' in people['d']['reason']
    assert not coverage['roster_complete']
    assert all('score' not in p for p in people.values())


def test_empty_coverage():
    empty=pd.DataFrame()
    match=SimpleNamespace(ticks_df=empty,kills=empty,shots=empty,damages=empty)
    assert finish_coverage(collect_coverage(match,empty,empty,5),[],[])['counts']['detected']==0


def test_metadata_only_participant_is_explicitly_unscored():
    empty=pd.DataFrame()
    match=SimpleNamespace(ticks_df=empty,kills=empty,shots=empty,damages=empty,
        participant_info=pd.DataFrame({'steamid':['76561198000000001'],'name':['Disconnected']}))
    coverage=finish_coverage(collect_coverage(match,empty,empty,5),[],[])
    assert coverage['counts']['detected']==1
    assert coverage['participants'][0]['reason']=='No tick telemetry observed for this participant.'


def frame():
    return pd.DataFrame(dict(demo_id=['one','one','two','two'],attacker_steamid=['a','b','a','b'],score=[.1,.9,.2,.8]))


def test_unlabeled_never_gets_accuracy():
    assert evaluate(frame(),bootstrap=0)['supervised'] is None


@pytest.mark.parametrize('score',[np.nan,np.inf,-.1,1.1])
def test_invalid_scores_rejected(score):
    df=frame();df.loc[0,'score']=score
    with pytest.raises(ValueError):validate(df)


def test_duplicate_rejected():
    with pytest.raises(ValueError):validate(pd.concat([frame(),frame()]))


def test_group_bootstrap_reproducible_and_partial_labels_excluded_from_ranking():
    df=frame();df['label']=[0,1,None,1]
    a=evaluate(df,10,42);b=evaluate(df,10,42)
    assert a==b
    assert a['ranking']['1']['complete_matches']==1
    assert a['ranking']['1']['mean_precision_at_k']==1
    assert a['supervised']['n']==3


def test_calibration_one_in_last_bin():
    rows=reliability(np.array([0,1]),np.array([0.,1.]))
    assert sum(x['n'] for x in rows)==2


def test_legacy_report_and_new_coverage_preserve_score_order(tmp_path):
    from main.ui.api.tests.test_desktop_result import fixture
    from main.ui.api.desktop_result import read_result
    import json
    fixture(tmp_path)
    old=read_result(tmp_path,'TEST_report','m.dem')
    assert old['coverage'] is None
    coverage=dict(schema_version='nullcs.coverage.v1',participants=[dict(steamid=p['steamid'],status='scored') for p in old['players']])
    (tmp_path/'player_coverage.json').write_text(json.dumps(coverage))
    assert read_result(tmp_path,'TEST_report','m.dem')['players']==old['players']
    coverage['participants'].pop()
    (tmp_path/'player_coverage.json').write_text(json.dumps(coverage))
    with pytest.raises(ValueError):read_result(tmp_path,'TEST_report','m.dem')
