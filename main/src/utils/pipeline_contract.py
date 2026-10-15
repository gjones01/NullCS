"""Bind corrected inference semantics to a complete, trusted local model bundle.

Hashes detect mixed/corrupt artifacts, not malicious replacement of the whole
bundle. Installer/release authenticity remains a separate responsibility.
"""
import hashlib
import json
import math
from pathlib import Path


def file_sha256(path: Path) -> str:
    digest=hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b''): digest.update(chunk)
    return digest.hexdigest()


def load_pipeline_contract(model_path: Path) -> dict | None:
    manifest_path=model_path.with_name(model_path.stem+'_training_manifest.json')
    manifest=json.loads(manifest_path.read_text(encoding='utf8')) if manifest_path.exists() else {}
    semantics=manifest.get('pipeline_semantics','legacy-v1')
    path=model_path.with_name(model_path.stem+'_pipeline_contract.json')
    if semantics=='legacy-v1' and not path.exists(): return None
    if semantics!='corrected-v2': raise ValueError('Unknown or inconsistent model pipeline semantics')
    contract=json.loads(path.read_text(encoding='utf8'))
    if contract.get('schema')!='nullcs.pipeline.v2' or contract.get('encounter_aggregation')!='aligned-v2':
        raise ValueError('Unsupported corrected pipeline contract')
    if manifest.get('train_data_mode')!='cs2cd': raise ValueError('Corrected contract currently supports cs2cd only')
    required={model_path.name,model_path.stem+'_features.txt',model_path.stem+'_training_manifest.json',
        model_path.stem+'_calibration.pkl','encounter_nn_cs2cd.pt','encounter_nn_cs2cd_features.json',
        'encounter_nn_cs2cd_preproc.pkl','encounter_nn_cs2cd_training_manifest.json'}
    artifacts=contract.get('artifact_sha256',{})
    if set(artifacts)!=required: raise ValueError('Incomplete corrected artifact bundle')
    for filename,digest in artifacts.items():
        if Path(filename).name!=filename or file_sha256(model_path.parent/filename)!=digest:
            raise ValueError(f'Pipeline artifact hash mismatch: {filename}')
    refs=contract.get('shrinkage_references',{})
    if set(refs)!={'rt_median','rt_p10','rt_p90','dist_median'} or not all(
        isinstance(v,(float,int)) and not isinstance(v,bool) and math.isfinite(v) for v in refs.values()
    ): raise ValueError('Invalid fitted shrinkage references')
    return contract
