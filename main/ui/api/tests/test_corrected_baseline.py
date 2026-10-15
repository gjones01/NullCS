import sys
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from src.models.encounter_nn import aggregate_encounter_scores
from src.features.aggregate_player_features import aggregate_kill_and_encounter_frames, build_encounter_row, ENCOUNTER_FEATURE_SPECS
from src.utils.research_splits import connected_groups, nested_plan, assert_disjoint_groups
from src.utils.pipeline_contract import load_pipeline_contract, file_sha256


def test_conditional_scores_follow_original_encounter_identity():
    frame = pd.DataFrame(dict(demo_id=['a']*3, attacker_steamid=['1']*3,
        encounter_nn_score=[.1,.9,.2], encounter_nn_hard=[1,0,0],
        encounter_nn_low_vis=[1,0,0], encounter_nn_kill_end=[1,0,0]), index=[7,3,5])
    legacy = aggregate_encounter_scores(frame).iloc[0]
    corrected = aggregate_encounter_scores(frame, semantics='aligned-v2').iloc[0]
    assert legacy.enn_hard_mean == .9
    assert corrected.enn_hard_mean == corrected.enn_low_vis_mean == .1
    assert legacy.enn_kill_end_mean == corrected.enn_kill_end_mean == .1
    for column in corrected.index.difference(['enn_hard_mean','enn_low_vis_mean']):
        assert corrected[column] == legacy[column]
    pd.testing.assert_frame_equal(aggregate_encounter_scores(frame, semantics='aligned-v2'),
        aggregate_encounter_scores(frame.iloc[::-1], semantics='aligned-v2'))
    with pytest.raises(ValueError):
        aggregate_encounter_scores(frame, semantics='typo')


def kills(demo, rt):
    return pd.DataFrame(dict(demo_id=[demo]*10,map_name=['map']*10,attacker_steamid=['1']*10,
        attacker_name=['name']*10,label=[0]*10,victim_steamid=['2']*10,weapon=['ak47']*10,
        kill_tick=np.arange(10)*64,rt_ticks=[rt]*10,distance=[500.]*10,round_num=list(range(10)),
        headshot=[False]*10,is_thrusmoke=[False]*10,is_micropeek_4=[False]*10))


def test_train_references_are_independent_of_heldout_data_and_batching():
    training, heldout = kills('train', 10.), kills('test', 100.)
    batch = aggregate_kill_and_encounter_frames(pd.concat([training,heldout]), shrinkage_fit_demo_ids={'train'})
    references = batch.attrs['shrinkage_references']
    assert references['rt_median'] == 10.
    alone = aggregate_kill_and_encounter_frames(heldout, shrinkage_references=references)
    assert alone.rt_median_shrunk.iloc[0] == 55.
    pd.testing.assert_frame_equal(batch[batch.demo_id=='test'].reset_index(drop=True), alone.reset_index(drop=True))
    mutated = aggregate_kill_and_encounter_frames(pd.concat([training,kills('test',900.)]), shrinkage_fit_demo_ids={'train'})
    assert mutated.attrs['shrinkage_references'] == references
    pd.testing.assert_frame_equal(batch[batch.demo_id=='train'].reset_index(drop=True),mutated[mutated.demo_id=='train'].reset_index(drop=True))
    with pytest.raises(ValueError):
        aggregate_kill_and_encounter_frames(training, shrinkage_fit_demo_ids={'missing'})
    with pytest.raises(ValueError):
        aggregate_kill_and_encounter_frames(training, shrinkage_references={})


def test_nested_splits_keep_transitive_players_and_duplicates_together():
    records=[dict(demo_id=str(i),tokens=[]) for i in range(60)]
    records[0]['tokens']=['player:123']
    records[1]['tokens']=['player:123','bytes:abc']
    records[2]['tokens']=['bytes:abc']
    groups=connected_groups(records)
    assert groups['0']==groups['1']==groups['2']
    assert groups==connected_groups(list(reversed(records)))
    plan=nested_plan(groups)
    assert sorted(d for p in plan for d in p['test'])==sorted(groups)
    for p in plan:
        assert_disjoint_groups({k:p[k] for k in ('development','calibration','test')},groups)
        assert sorted(d for f in p['cnn_crossfit'] for d in f['heldout'])==sorted(p['development'])
        for f in p['cnn_crossfit']:
            assert_disjoint_groups(dict(**f,calibration=p['calibration'],test=p['test']),groups)
    with pytest.raises(ValueError):
        assert_disjoint_groups(dict(fit=['0'],test=['2']),groups)


def test_joint_only_optimization_preserves_every_retained_value():
    frame=pd.DataFrame({column:[0.,np.nan,5.,1000.] for column in ENCOUNTER_FEATURE_SPECS})
    frame=frame.assign(demo_id='a',map_name='map',attacker_steamid='1',attacker_name='name',label=0,
        start_tick=[4,2,3,1],ended_in_kill_within_y=[False,True,True,False])
    full=build_encounter_row(frame)
    optimized=build_encounter_row(frame,joint_only=True)
    assert {k:full[k] for k in optimized}==optimized


def test_corrected_bundle_rejects_missing_mixed_and_nonfinite_artifacts(tmp_path):
    model=tmp_path/'xgb_player_level_cs2cd.json'
    stem=model.stem
    assert load_pipeline_contract(model) is None  # old artifacts retain legacy semantics
    manifest=tmp_path/(stem+'_training_manifest.json')
    manifest.write_text(json.dumps(dict(pipeline_semantics='corrected-v2',train_data_mode='cs2cd')))
    with pytest.raises(FileNotFoundError): load_pipeline_contract(model)
    names=[model.name,stem+'_features.txt',stem+'_calibration.pkl','encounter_nn_cs2cd.pt',
        'encounter_nn_cs2cd_features.json','encounter_nn_cs2cd_preproc.pkl','encounter_nn_cs2cd_training_manifest.json']
    for name in names: (tmp_path/name).write_bytes(b'fixture')
    contract=dict(schema='nullcs.pipeline.v2',encounter_aggregation='aligned-v2',
        artifact_sha256={name:file_sha256(tmp_path/name) for name in names+[manifest.name]},
        shrinkage_references=dict(rt_median=10.,rt_p10=1.,rt_p90=20.,dist_median=500.))
    path=tmp_path/(stem+'_pipeline_contract.json')
    path.write_text(json.dumps(contract))
    assert load_pipeline_contract(model)==contract
    model.write_bytes(b'mixed-model')
    with pytest.raises(ValueError,match='hash mismatch'): load_pipeline_contract(model)
    model.write_bytes(b'fixture')
    contract['shrinkage_references']['rt_median']=float('nan')
    path.write_text(json.dumps(contract))
    with pytest.raises(ValueError,match='shrinkage'): load_pipeline_contract(model)
    contract['artifact_sha256']['../outside']='unused'
    path.write_text(json.dumps(contract))
    with pytest.raises(ValueError,match='Incomplete'): load_pipeline_contract(model)
