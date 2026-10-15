"""Compare two repeated experimental folds without fitting or changing artifacts."""
import argparse
import json
from pathlib import Path

import pandas as pd
import torch

from research_validation import sha256


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--first',type=Path,required=True)
    ap.add_argument('--repeat',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    if args.output.exists(): raise FileExistsError(args.output)
    runs=[json.loads((p/'run.json').read_text()) for p in [args.first,args.repeat]]
    for key in ['input_manifest_sha256','fold','cnn','epochs','seed','aggregation','shrinkage']:
        if runs[0][key]!=runs[1][key]: raise ValueError(f'Not the same experiment: {key}')
    if any(r['status']!='complete' for r in runs): raise ValueError('Incomplete run')
    first=pd.read_parquet(args.first/'test_predictions.parquet')
    repeat=pd.read_parquet(args.repeat/'test_predictions.parquet')
    pd.testing.assert_frame_equal(first,repeat,check_exact=True)
    identical={}
    for name in ['cnn_final']+[f'cnn_oof_{i}' for i in range(4)]:
        a=torch.load(args.first/name/'weights.pt',weights_only=True,map_location='cpu')
        b=torch.load(args.repeat/name/'weights.pt',weights_only=True,map_location='cpu')
        identical[name]=a.keys()==b.keys() and all(torch.equal(a[k],b[k]) for k in a)
    if not all(identical.values()): raise ValueError('CNN states differ')
    result=dict(test_rows=len(first),predictions_bit_identical=True,cnn_states_bit_identical=identical,
        first_run_sha256=sha256(args.first/'run.json'),repeat_run_sha256=sha256(args.repeat/'run.json'),
        scope='One full experimental fold repeated on this machine; not a cross-hardware guarantee')
    args.output.write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(result))


if __name__=='__main__': main()
