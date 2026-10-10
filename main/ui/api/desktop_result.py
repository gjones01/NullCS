"""Small desktop contract. Read canonical outputs; never recompute rankings or scores."""
import json
import math
import re
from pathlib import Path
import pandas as pd


def finite(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def read_result(root: Path, job: str, filename: str) -> dict:
    data = pd.read_csv(root / 'ranked_players_infer.csv', dtype={'attacker_steamid': str})
    manifest = json.loads((root / 'infer_manifest.json').read_text(encoding='utf8'))
    trace = json.loads((root / 'debug_score_trace.json').read_text(encoding='utf8'))
    if data.empty or set(data['demo_id'].astype(str)) != {job} or manifest.get('demo_id') != job:
        raise ValueError('Incomplete or mismatched result')
    players = []
    for rank, (_, row) in enumerate(data.iterrows(), start=1):
        raw = finite(row.get('proba_cheater_infer'))
        risk = finite(row.get('risk'))
        if raw is None or risk is None:
            raise ValueError('Missing score')
        sid = str(row['attacker_steamid'])
        if not re.fullmatch(r'[0-9]{17}', sid):
            raise ValueError('Invalid player identifier')
        name = row.get('attacker_name')
        name = sid if pd.isna(name) else ' '.join(str(name).split())[:120]
        players.append(dict(rank=rank, steamid=sid,
            name=name,
            review_score=risk, model_score=raw,
            calibrated_probability=finite(row.get('proba_calibrated')),
            confidence=finite(row.get('confidence'))))
    warnings = ['Beta research output. Review the match before drawing conclusions.']
    if not trace.get('calibration_used'):
        warnings.append('Calibration is unavailable for this model; no calibrated estimate is shown.')
    log_path = root / 'logs' / 'pipeline.log'
    log = log_path.read_text(encoding='utf8', errors='replace') if log_path.exists() else ''
    if 'InconsistentVersionWarning' in log:
        warnings.append('The calibration file was saved with a different library version. Interpret estimates cautiously.')
    provenance = manifest.get('parser_provenance') or {}
    if provenance.get('demoparser2_version') == '0.41.4':
        warnings.append('This parser version can retain stale input values in some demos, which may affect scores.')
    return dict(schema_version='nullcs.desktop.v1', job_id=job, filename=filename,
        map_name=str(data['map_name'].iloc[0]), players=players, warnings=warnings,
        model=dict(name=Path(str(trace.get('model_artifact_path', ''))).name,
                   sha256=trace.get('model_sha256'), calibration_used=bool(trace.get('calibration_used'))),
        parser_version=provenance.get('demoparser2_version'))
