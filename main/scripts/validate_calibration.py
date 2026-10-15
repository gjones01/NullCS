"""Development-only calibration selection over frozen nested-pipeline predictions.

No CNN/XGBoost refitting, production writes, or external-demo labels.
Outer tests have already been inspected: this is continued internal validation.
"""
import argparse
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold

from research_validation import metrics, sha256

METHODS = ('raw', 'sigmoid', 'isotonic')
PROTOCOL = dict(scope='Continued internal validation; previously inspected outer tests',
    candidates=list(METHODS), calibration_cv_folds=3,
    selection='Lowest pooled calibration-CV log loss, then Brier, then candidate order; per outer fold',
    sigmoid='LogisticRegression(C=1, solver=lbfgs, max_iter=2000) on raw probability; no class weighting',
    thresholds=[.5, .8, .95], seed=20261015,
    safeguards='No outer-test selection, clipping adjustment, new model fit or production promotion')


def check_frame(frame):
    if frame.empty or frame.duplicated(['demo_id', 'attacker_steamid']).any():
        raise ValueError('Empty or duplicate player-match predictions')
    if frame[['demo_id', 'attacker_steamid', 'label', 'raw_score']].isna().any().any():
        raise ValueError('Missing identity, label or score')
    if not frame.label.isin([0, 1]).all() or not np.isfinite(frame.raw_score).all() or not frame.raw_score.between(0, 1).all():
        raise ValueError('Invalid labels or probabilities')


def fit_predict(method, fit, predict):
    if method == 'raw':
        return predict.raw_score.to_numpy(dtype=float)
    if set(fit.label.unique()) != {0, 1}:
        raise ValueError('Calibration training split needs both classes')
    if method == 'isotonic':
        model = IsotonicRegression(out_of_bounds='clip').fit(fit.raw_score, fit.label)
        return model.predict(predict.raw_score)
    if method == 'sigmoid':
        model = LogisticRegression(C=1, solver='lbfgs', max_iter=2000, random_state=20261015)
        model.fit(fit[['raw_score']], fit.label)
        return model.predict_proba(predict[['raw_score']])[:, 1]
    raise ValueError('Unknown calibration method')


def select_method(calibration, groups):
    """Only the calibration partition is accepted; outer-test labels cannot select a method."""
    check_frame(calibration)
    components = calibration.demo_id.map(groups)
    if components.isna().any() or components.nunique() < 3:
        raise ValueError('Need three known calibration groups')
    predictions = {m: np.empty(len(calibration)) for m in METHODS}
    memberships = []
    for fit_idx, hold_idx in GroupKFold(3).split(calibration, groups=components):
        fit, held = calibration.iloc[fit_idx], calibration.iloc[hold_idx]
        if set(components.iloc[fit_idx]) & set(components.iloc[hold_idx]):
            raise ValueError('Calibration group overlap')
        memberships.append(dict(fit_demos=sorted(fit.demo_id.unique()), heldout_demos=sorted(held.demo_id.unique())))
        for method in METHODS:
            predictions[method][hold_idx] = fit_predict(method, fit, held)
    scores = {m: metrics(calibration.label, p) for m, p in predictions.items()}
    selected = min(METHODS, key=lambda m: (scores[m]['log_loss'], scores[m]['brier'], METHODS.index(m)))
    return selected, scores, memberships


def threshold_counts(frame, column, match_labels=None):
    rows = []
    for threshold in PROTOCOL['thresholds']:
        flag = frame[column] >= threshold
        negative = frame.label.eq(0)
        observed = frame.groupby('demo_id').label.max()
        negative_matches = (observed if match_labels is None else match_labels.reindex(observed.index)).eq(0)
        flagged_matches = frame.assign(flag=flag).groupby('demo_id').flag.max()
        rows.append(dict(threshold=threshold, negative_players=int(negative.sum()),
            flagged_negative_players=int((negative & flag).sum()),
            positive_players=int((~negative).sum()), flagged_positive_players=int((~negative & flag).sum()),
            scored_negative_matches=int(negative_matches.sum()),
            flagged_scored_negative_matches=int((negative_matches & flagged_matches).sum())))
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input', type=Path, required=True)
    ap.add_argument('--folds', type=Path, nargs=5, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output/'protocol.json').write_text(json.dumps(PROTOCOL, indent=2), encoding='utf8')
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from src.utils.research_splits import assert_disjoint_groups
    from src.utils.scoring import apply_rt_low_evidence_downweight
    snapshot = json.loads((args.input/'manifest.json').read_text())
    if sha256(args.input/'split_manifest.json') != snapshot['snapshot_hashes']['split_manifest.json']:
        raise ValueError('Changed split snapshot')
    split = json.loads((args.input/'split_manifest.json').read_text())
    label_frames = []
    for name in ('kills.parquet', 'encounters.parquet'):
        if sha256(args.input/name) != snapshot['snapshot_hashes'][name]:
            raise ValueError('Changed source labels')
        label_frames.append(pd.read_parquet(args.input/name, columns=['demo_id','attacker_steamid','label']))
    labels = pd.concat(label_frames, ignore_index=True).drop_duplicates()
    if labels.groupby(['demo_id','attacker_steamid']).label.nunique().gt(1).any():
        raise ValueError('Conflicting source labels')
    match_labels = labels.groupby('demo_id').label.max()
    frames, records, seen = [], [], set()
    for folder in args.folds:
        run = json.loads((folder/'run.json').read_text())
        fold = run['fold']
        if run['status'] != 'complete' or fold != split['folds'][fold['fold']] or fold['fold'] in seen:
            raise ValueError('Incomplete, changed or repeated fold')
        seen.add(fold['fold'])
        if run['input_manifest_sha256'] != sha256(args.input/'manifest.json'):
            raise ValueError('Wrong input snapshot')
        assert_disjoint_groups({k:fold[k] for k in ('development','calibration','test')}, split['groups'])
        for name in ('calibration_predictions.parquet', 'test_predictions.parquet'):
            if sha256(folder/name) != run['artifacts'][name]:
                raise ValueError('Predictions changed')
        cal = pd.read_parquet(folder/'calibration_predictions.parquet')
        if not set(cal.demo_id).issubset(fold['calibration']):
            raise ValueError('Calibration rows outside partition')
        selected, cv, memberships = select_method(cal, split['groups'])
        record = dict(fold=fold['fold'], selected=selected, calibration_cv=cv,
            cv_memberships=memberships, parent_run_sha256=sha256(folder/'run.json'))
        # Persist decision before opening this fold's outer-test values.
        (args.output/f'selection_{fold["fold"]}.json').write_text(json.dumps(record, indent=2), encoding='utf8')
        test = pd.read_parquet(folder/'test_predictions.parquet')
        check_frame(test)
        if not set(test.demo_id).issubset(fold['test']):
            raise ValueError('Test rows outside partition')
        for method in METHODS:
            test[method] = fit_predict(method, cal, test)
        test['selected'] = test[selected]
        test['selected_review'] = apply_rt_low_evidence_downweight(test.selected, test.rt_n)
        test['fold'] = fold['fold']
        test['component'] = test.demo_id.map(split['groups'])
        frames.append(test); records.append(record)
    if seen != set(range(5)):
        raise ValueError('Expected five different folds')
    frame = pd.concat(frames, ignore_index=True)
    check_frame(frame)
    if (frame.groupby('component').fold.nunique() > 1).any():
        raise ValueError('Group crosses outer tests')
    columns = [*METHODS, 'selected', 'selected_review']
    slices = dict(all_scored=frame, pro_assumed_negative=frame[frame.demo_id.str.startswith('CS2CD_PROLEGIT_')],
        negative_source=frame[frame.demo_id.str.startswith('CS2CD_no_cheater_present_')])
    results = {name: dict(rows=len(part), matches=int(part.demo_id.nunique()),
        metrics={c:metrics(part.label, part[c]) for c in columns},
        thresholds={c:threshold_counts(part,c,match_labels) for c in columns}) for name,part in slices.items() if len(part)}
    extremes = {c:dict(positive_at_zero=int(((frame.label==1)&(frame[c]==0)).sum()),
        negative_at_one=int(((frame.label==0)&(frame[c]==1)).sum())) for c in columns}
    frame.to_parquet(args.output/'predictions.parquet', index=False)
    retrieval = {}
    for column in ('raw','isotonic','selected_review'):
        retrieval[column] = []
        for k in (1,3,5):
            top = frame.sort_values([column,'attacker_steamid'],ascending=[False,True],kind='stable').groupby('demo_id').head(k)
            found = top.groupby('demo_id').label.max().eq(1).reindex(match_labels.index,fill_value=False)
            retrieval[column].append(dict(k=k,positive_matches=int(match_labels.eq(1).sum()),
                found=int((found & match_labels.eq(1)).sum())))
    per_fold = {str(i):{c:metrics(part.label,part[c]) for c in columns} for i,part in frame.groupby('fold')}
    report = dict(protocol=PROTOCOL, source_script_sha256=sha256(Path(__file__)),
        decisions=[{k:v for k,v in r.items() if k!='cv_memberships'} for r in records],
        results=results, extremes=extremes, per_fold=per_fold, review_retrieval=retrieval,
        ranking_ties='Ascending player ID, unchanged from prior internal reporting; ties can affect retrieval.',
        coverage=dict(source_matches=len(match_labels),scored_matches=int(frame.demo_id.nunique()),
            observed_player_matches=len(labels),scored_player_matches=len(frame),
            note='Threshold counts cover scored records only; unscored participants are not correct negatives. Source event participants are not a verified full roster.'),
        limitations='Historical source labels, incomplete repeated-player identity, previously inspected tests, and one 95-match group. No independent accuracy claim; no production changes.')
    (args.output/'summary.json').write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf8')
    print(json.dumps(dict(selected=[r['selected'] for r in records],
        log_loss={c:results['all_scored']['metrics'][c]['log_loss'] for c in columns},extremes=extremes)))


if __name__ == '__main__':
    main()
