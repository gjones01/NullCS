from __future__ import annotations

import numpy as np
import pandas as pd


def build_sample_weights(
    df: pd.DataFrame,
    demo_ids: list[str],
    positive_demo_weight: float,
) -> tuple[np.ndarray | None, dict[str, int]]:
    """Optional extra sample weight for positive rows of chosen demos.

    Single source of truth for training and evaluation (AUDIT.md finding F11).
    Returns ``(None, {})`` when no reweighting is requested: an all-ones weight
    vector and ``None`` are bit-identical for XGBoost, verified on the
    ``n_players >= 8`` CS2CD table (max abs probability difference 0.0), so the
    result can be passed straight to ``fit(sample_weight=...)``.
    """
    normalized = {str(x).strip() for x in demo_ids if str(x).strip()}
    if not normalized or float(positive_demo_weight) == 1.0:
        return None, {"weighted_positive_rows": 0, "weighted_demos_found": 0}

    weights = np.ones(len(df), dtype=float)
    mask = df["demo_id"].astype(str).isin(normalized) & (df["label"].astype(int) == 1)
    weights[mask.to_numpy()] = float(positive_demo_weight)
    stats = {
        "weighted_positive_rows": int(mask.sum()),
        "weighted_demos_found": int(df.loc[df["demo_id"].astype(str).isin(normalized), "demo_id"].nunique()),
    }
    return weights, stats