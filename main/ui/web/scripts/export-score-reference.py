"""Export aggregate historical OOF context, without identities or changing scores.

Run with --data-root pointing at main/data/processed. Reject inconsistent records.
The UI bands are presentation choices using tested raw-score cutoffs, not new
classification thresholds or evidence of performance on a user's match.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-root', type=Path, required=True)
    args = parser.parse_args()
    root = args.data_root
    oof = root/'reports/player_oof_predictions_cs2cd.csv'
    summary_path = root/'models/xgb_player_level_cs2cd_eval_summary.json'
    summary = json.loads(summary_path.read_text())
    data = pd.read_csv(oof, usecols=['demo_id', 'y_true', 'proba_raw_oof', 'fold_id'])
    scores = data.proba_raw_oof.to_numpy()
    labels = data.y_true.to_numpy()
    assert np.isfinite(scores).all() and ((scores >= 0) & (scores <= 1)).all()
    assert set(labels) == {0, 1} and set(data.fold_id) == {1, 2, 3, 4, 5}
    assert data.groupby('demo_id').fold_id.nunique().eq(1).all()
    assert len(data) == summary['rows'] and data.demo_id.nunique() == summary['demos']
    thresholds = []
    for text, expected in summary['thresholds'].items():
        threshold = float(text)
        pred, actual = scores >= threshold, labels == 1
        counts = dict(tp=int((pred & actual).sum()), fp=int((pred & ~actual).sum()),
                      fn=int((~pred & actual).sum()), tn=int((~pred & ~actual).sum()))
        assert all(counts[k] == expected[k] for k in counts), text
        thresholds.append(dict(threshold=threshold, **counts))
    bins = np.linspace(0, 1, 21)
    result = dict(schema_version=1, source='Historical CS2CD grouped out-of-fold evaluation',
        score='proba_raw_oof', rows=len(data), demos=int(data.demo_id.nunique()),
        negative=int((labels == 0).sum()), positive=int((labels == 1).sum()),
        model_sha256=sha(root/'models/xgb_player_level_cs2cd.json'),
        source_sha256=sha(oof), summary_sha256=sha(summary_path),
        edges=bins.tolist(), thresholds=thresholds,
        negative_counts=np.histogram(scores[labels == 0], bins)[0].tolist(),
        positive_counts=np.histogram(scores[labels == 1], bins)[0].tolist(),
        note='Historical fold-model scores, not an independent production test. Dataset labels and cohort mix affect interpretation. Bands use tested cutoffs selected for display; no optimal decision rule is claimed.')
    output = Path(__file__).resolve().parents[1]/'src/lib/score-reference.json'
    output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf8')
    print(f'Exported {len(data)} rows as anonymous aggregate counts to {output.name}')

if __name__ == '__main__':
    main()
