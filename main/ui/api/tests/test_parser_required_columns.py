"""Verify every required tick-column guard without changing parser semantics."""
from types import SimpleNamespace
import pandas as pd
import pytest
from main.src.adapters.demoparser2_local import CRITICAL_TICK_COLUMNS, MODEL_TICK_COLUMNS, _ticks_table


@pytest.mark.parametrize('missing', sorted(CRITICAL_TICK_COLUMNS | MODEL_TICK_COLUMNS))
def test_missing_required_column_is_rejected(missing):
    frame = pd.DataFrame({name: [0] for name in (CRITICAL_TICK_COLUMNS | MODEL_TICK_COLUMNS) - {missing}})
    parser = SimpleNamespace(parse_ticks=lambda _: frame)
    with pytest.raises(RuntimeError, match='tick schema is missing'):
        _ticks_table(parser)
