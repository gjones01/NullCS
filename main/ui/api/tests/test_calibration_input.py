import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.calibrate_model import load_oof


def test_ambiguous_calibration_files_require_explicit_choice(tmp_path):
    csv = tmp_path / 'predictions.csv'
    parquet = tmp_path / 'predictions.parquet'
    pd.DataFrame({'y_true': [0, 1], 'proba_raw_oof': [.1, .9]}).to_csv(csv, index=False)
    pd.DataFrame({'y_true': [0, 1], 'proba_raw_oof': [.4, .6]}).to_parquet(parquet)
    with pytest.raises(ValueError, match='Both CSV and Parquet'):
        load_oof(csv, parquet)
    assert load_oof(csv, parquet, csv).proba_raw_oof.tolist() == [.1, .9]
    assert load_oof(csv, parquet, parquet).proba_raw_oof.tolist() == [.4, .6]


def test_single_missing_and_unsupported_calibration_inputs(tmp_path):
    csv = tmp_path / 'predictions.csv'
    parquet = tmp_path / 'predictions.parquet'
    with pytest.raises(FileNotFoundError):
        load_oof(csv, parquet)
    pd.DataFrame({'y_true': [0], 'proba_raw_oof': [.1]}).to_csv(csv, index=False)
    assert len(load_oof(csv, parquet)) == 1
    with pytest.raises(ValueError, match='CSV or Parquet'):
        load_oof(csv, parquet, tmp_path / 'unsupported.json')
