"""Read-only evaluation of saved predictions. No training or production writes.

CSV schema: demo_id, attacker_steamid, score; optional label (0/1 or blank),
cohort, map_name. Labels must be independently supplied, never inferred from score.
Run folders must be new. Inputs/seed/config are hashed in the output manifest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def reliability(y, p, bins=10):
    ids = np.minimum((np.asarray(p) * bins).astype(int), bins - 1)
    rows = []
    for i in range(bins):
        mask = ids == i
        if mask.any():
            rows.append(dict(lower=i / bins, upper=(i + 1) / bins, n=int(mask.sum()),
                             prediction=float(np.mean(p[mask])), observed=float(np.mean(y[mask]))))
    return rows


def metrics(y, p):
    y, p = np.asarray(y, dtype=int), np.asarray(p, dtype=float)
    curve = reliability(y, p)
    return dict(n=len(y), positive=int(y.sum()), prevalence=float(y.mean()),
        roc_auc=float(roc_auc_score(y, p)) if len(np.unique(y)) == 2 else None,
        average_precision=float(average_precision_score(y, p)) if y.sum() else None,
        brier=float(brier_score_loss(y, p)),
        log_loss=float(log_loss(y, p, labels=[0, 1])),
        ece_10_equal_width=float(sum(r['n'] * abs(r['prediction'] - r['observed']) for r in curve) / len(y)),
        reliability=curve)


def validate(frame):
    required = {'demo_id', 'attacker_steamid', 'score'}
    if not required.issubset(frame):
        raise ValueError(f'Missing columns: {sorted(required - set(frame))}')
    frame = frame.copy()
    for c in ['demo_id', 'attacker_steamid']:
        if frame[c].isna().any() or frame[c].astype(str).str.strip().eq('').any():
            raise ValueError(f'Missing identity: {c}')
    if frame.duplicated(['demo_id', 'attacker_steamid']).any():
        raise ValueError('Duplicate player-match rows; resolve before evaluation')
    frame['score'] = pd.to_numeric(frame['score'], errors='raise')
    if not np.isfinite(frame['score']).all() or not frame['score'].between(0, 1).all():
        raise ValueError('Scores must be finite and in [0, 1]')
    if 'label' not in frame:
        frame['label'] = np.nan
    present = frame['label'].notna()
    frame.loc[present, 'label'] = pd.to_numeric(frame.loc[present, 'label'], errors='raise')
    if not frame.loc[present, 'label'].isin([0, 1]).all():
        raise ValueError('Labels must be 0, 1 or absent')
    return frame


def evaluate(frame, bootstrap=200, seed=20261014):
    frame = validate(frame)
    labeled = frame[frame.label.notna()]
    out = dict(rows=len(frame), demos=int(frame.demo_id.nunique()), labeled_rows=len(labeled),
        score_quantiles={str(q): float(frame.score.quantile(q)) for q in [0, .1, .5, .9, 1]} if len(frame) else {},
        limitations=['Unlabeled rows measure score behavior, not accuracy.',
                      'Match bootstrap does not correct player/source overlap or model-selection bias.',
                      'ECE depends on bins and cohort size; it is not proof of calibrated probabilities.'])
    if labeled.empty:
        out['supervised'] = None
        return out
    out['supervised'] = metrics(labeled.label.to_numpy(), labeled.score.to_numpy())
    out['thresholds'] = []
    for t in [.2, .5]:
        pred, y = labeled.score >= t, labeled.label == 1
        tp, fp, fn, tn = int((pred & y).sum()), int((pred & ~y).sum()), int((~pred & y).sum()), int((~pred & ~y).sum())
        out['thresholds'].append(dict(threshold=t, tp=tp, fp=fp, fn=fn, tn=tn,
            precision=tp/(tp+fp) if tp+fp else None, recall=tp/(tp+fn) if tp+fn else None,
            false_positive_rate=fp/(fp+tn) if fp+tn else None))
    # Partial labels cannot define the relevance of the whole ranked match.
    complete = [g for _, g in frame.groupby('demo_id') if g.label.notna().all()]
    out['ranking'] = {}
    for k in [1, 3]:
        precision, recall = [], []
        for g in complete:
            g = g.sort_values(['score', 'attacker_steamid'], ascending=[False, True], kind='stable')
            hits = int(g.head(k).label.sum())
            precision.append(hits/min(k, len(g)))
            if g.label.sum():
                recall.append(hits/float(g.label.sum()))
        out['ranking'][str(k)] = dict(complete_matches=len(complete),
            mean_precision_at_k=float(np.mean(precision)) if precision else None,
            mean_recall_at_k_positive_matches=float(np.mean(recall)) if recall else None,
            tie_break='SteamID ascending; diagnostic raw-score ranking, not production review order')
    rng = np.random.default_rng(seed)
    groups = [g for _, g in labeled.groupby('demo_id')]
    values = {k: [] for k in ['roc_auc', 'average_precision', 'brier']}
    for _ in range(bootstrap):
        sample = pd.concat([groups[i] for i in rng.integers(0, len(groups), len(groups))])
        m = metrics(sample.label.to_numpy(), sample.score.to_numpy())
        for key in values:
            if m[key] is not None:
                values[key].append(m[key])
    out['match_bootstrap_95_percentile'] = {k: dict(interval=np.quantile(v, [.025, .975]).tolist() if v else None, valid_replicates=len(v)) for k, v in values.items()}
    out['slices'] = {}
    for c in ['cohort', 'map_name']:
        if c in labeled:
            out['slices'][c] = {str(key): metrics(g.label.to_numpy(), g.score.to_numpy()) for key, g in labeled.groupby(c)}
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--predictions', required=True, type=Path)
    ap.add_argument('--output', required=True, type=Path)
    ap.add_argument('--bootstrap', type=int, default=200)
    ap.add_argument('--seed', type=int, default=20261014)
    ap.add_argument('--reference-features', type=Path)
    ap.add_argument('--features', type=Path)
    args = ap.parse_args()
    if not 0 <= args.bootstrap <= 10000:
        ap.error('bootstrap must be between 0 and 10000')
    frame = pd.read_csv(args.predictions, dtype={'demo_id':str, 'attacker_steamid':str})
    result = evaluate(frame, args.bootstrap, args.seed)
    manifest = dict(predictions_sha256=sha256(args.predictions), seed=args.seed, bootstrap=args.bootstrap)
    if args.features and args.reference_features:
        current, reference = pd.read_parquet(args.features), pd.read_parquet(args.reference_features)
        drift = []
        for c in sorted(set(current.select_dtypes('number')) & set(reference.select_dtypes('number')) - {'label'}):
            r, x = reference[c].replace([np.inf,-np.inf], np.nan), current[c].replace([np.inf,-np.inf], np.nan)
            lo, hi = r.quantile([.01,.99]); valid = x.dropna()
            drift.append(dict(feature=c, missing_fraction=float(x.isna().mean()),
                outside_reference_1_99=float(((valid < lo) | (valid > hi)).mean()) if len(valid) else None))
        result['feature_shift'] = drift
        result['limitations'].append('Marginal reference-tail rates are shift flags, not multivariate OOD probabilities.')
        manifest.update(features_sha256=sha256(args.features), reference_sha256=sha256(args.reference_features))
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output/'metrics.json').write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf8')
    (args.output/'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf8')
    print(args.output)


if __name__ == '__main__':
    main()
