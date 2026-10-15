"""Generate aggregate-only benchmark JSON and figures from verified completed folds.

This creates local publication assets; it does not upload files or deploy a site.
"""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from research_validation import sha256


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--summary',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--figures',type=Path,required=True)
    args=ap.parse_args()
    source=json.loads(args.summary.read_text())
    frames=[]
    for directory,digest in source['run_hashes'].items():
        path=Path(directory)
        if sha256(path/'run.json')!=digest: raise ValueError('Run changed since summary')
        run=json.loads((path/'run.json').read_text())
        if sha256(path/'test_predictions.parquet')!=run['artifacts']['test_predictions.parquet']:
            raise ValueError('Predictions changed since evaluation')
        frames.append(pd.read_parquet(path/'test_predictions.parquet'))
    frame=pd.concat(frames,ignore_index=True)
    public={k:source[k] for k in ['scope','rows','demos','components','metrics','coverage','review_retrieval',
        'source_slices','raw_score_component_bootstrap_95','bootstrap_replicates','seed','limitations','fold_seconds']}
    public.update(schema='nullcs.internal-benchmark.v1',date='2026-10-14',
        configuration=dict(context_pre_ticks=128,context_post_ticks=16,observations=32,channels=35,player_features=449,
            outer_folds=5,cnn_crossfit_folds=4,cnn_epochs=4,cnn_fits=25,xgb_fits=5,calibration_fits=5),
        source_summary_sha256=sha256(args.summary),run_sha256=list(source['run_hashes'].values()),
        production_model_replaced=False)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.figures.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(public,indent=2,allow_nan=False)+'\n',encoding='utf8')
    plt.rcParams.update({'figure.facecolor':'#101513','axes.facecolor':'#101513','text.color':'#e4e5de',
        'axes.labelcolor':'#e4e5de','xtick.color':'#b3bcb4','ytick.color':'#b3bcb4','axes.edgecolor':'#67706a',
        'font.size':11,'savefig.facecolor':'#101513'})
    fig,ax=plt.subplots(figsize=(10,6))
    for label,color,title in [(0,'#9eaaa3','Negative source labels'),(1,'#ced5b2','Positive source labels')]:
        values=frame.loc[frame.label==label,'raw_score']
        counts,edges=np.histogram(values,bins=np.linspace(0,1,21))
        ax.stairs(counts/len(values)*100,edges,label=f'{title} (n={len(values):,})',color=color,linewidth=2)
    ax.set(xlabel='Raw model score',ylabel='Share of label group (%)',title='Corrected internal evaluation / raw-score distributions')
    ax.legend(frameon=False)
    fig.text(.1,.015,'Historical source labels; not independently verified real-world accuracy.',fontsize=9)
    fig.tight_layout(rect=(0,.035,1,1));fig.savefig(args.figures/'corrected-score-distributions.png',dpi=160);plt.close(fig)
    fig,ax=plt.subplots(figsize=(10,6))
    ax.plot([0,1],[0,1],color='#67706a',linestyle='--',label='Perfect calibration')
    for column,color,title in [('raw_score','#9eaaa3','Raw'),('calibrated_probability','#ced5b2','Isotonic calibrated')]:
        bins=source['metrics'][column]['reliability']
        ax.plot([b['prediction'] for b in bins],[b['observed'] for b in bins],marker='o',color=color,label=title)
    ax.set(xlabel='Mean predicted score / probability',ylabel='Observed positive-label fraction',xlim=(0,1),ylim=(0,1),title='Disjoint calibration evaluation / pooled outer test predictions')
    ax.legend(frameon=False)
    fig.text(.1,.015,'Calibration improves Brier error but worsens log loss. Release promotion remains blocked.',fontsize=9)
    fig.tight_layout(rect=(0,.035,1,1));fig.savefig(args.figures/'corrected-calibration.png',dpi=160);plt.close(fig)
    fig,ax=plt.subplots(figsize=(10,6))
    rows=source['review_retrieval']; values=[100*r['positive_matches_retrieved']/r['positive_matches'] for r in rows]
    ax.bar([f'Top {r["k"]}' for r in rows],values,color='#bfc8a9',width=.5)
    for i,r in enumerate(rows):
        ax.text(i,values[i]+2,f'{values[i]:.1f}%\n{r["positive_matches_retrieved"]} / {r["positive_matches"]}',ha='center')
    ax.set(ylim=(0,105),ylabel='Positive-label matches retrieved (%)',title='Review-score retrieval / includes unscored positive matches')
    fig.text(.1,.015,'Player-ID tie break; full tie bounds and eligibility coverage accompany the benchmark JSON.',fontsize=9)
    fig.tight_layout(rect=(0,.035,1,1));fig.savefig(args.figures/'corrected-review-retrieval.png',dpi=160);plt.close(fig)


if __name__=='__main__': main()
