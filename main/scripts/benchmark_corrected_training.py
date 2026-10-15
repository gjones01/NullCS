"""Bounded real-data training-step benchmark. Writes no predictive artifact."""
import argparse
import json
from pathlib import Path
import sys
import time

import numpy as np
import torch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.models.encounter_nn import build_model, fit_temporal_preprocessor, temporal_channel_columns


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--device',choices=['cpu','cuda'],required=True)
    args=ap.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    if args.device=='cuda' and not torch.cuda.is_available():
        raise RuntimeError('CUDA unavailable')
    torch.set_num_threads(4)
    torch.manual_seed(20261014)
    raw=np.load(args.input/'temporal.npy',mmap_mode='r',allow_pickle=False)
    import pandas as pd
    frame=pd.read_parquet(args.input/'encounters.parquet')
    selection=np.random.default_rng(20261014).choice(len(raw),2048,replace=False)
    x_raw=raw[selection]
    preproc=fit_temporal_preprocessor(x_raw,temporal_channel_columns(),32)
    x=torch.from_numpy(preproc.transform_array(x_raw)).to(args.device)
    y=torch.from_numpy(frame.iloc[selection].label.to_numpy(dtype=np.float32)).to(args.device)
    model=build_model(35,model_type='temporal_cnn').to(args.device)
    optimizer=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.0001)
    loss_fn=torch.nn.BCEWithLogitsLoss()
    times=[]
    for step in range(6):
        if args.device=='cuda': torch.cuda.synchronize()
        start=time.perf_counter()
        optimizer.zero_grad(set_to_none=True)
        loss=loss_fn(model(x),y)
        if not torch.isfinite(loss): raise ValueError('Nonfinite benchmark loss')
        loss.backward(); optimizer.step()
        if args.device=='cuda': torch.cuda.synchronize()
        if step: times.append(time.perf_counter()-start)
    result=dict(device=args.device,torch=torch.__version__,cuda=torch.version.cuda,
        batch=2048,observations=32,channels=35,threads=4,steps_seconds=times,
        median_seconds=float(np.median(times)),scope='real-data kernel benchmark, not full training duration',
        peak_cuda_bytes=torch.cuda.max_memory_allocated() if args.device=='cuda' else None)
    args.output.write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(result),flush=True)


if __name__=='__main__': main()
