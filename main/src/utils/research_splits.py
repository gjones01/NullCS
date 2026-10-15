"""Group-first development splits. Anonymous slot IDs are not player identities."""
from __future__ import annotations

import hashlib
import pandas as pd
from sklearn.model_selection import GroupKFold


def connected_groups(records: list[dict]) -> dict[str, str]:
    """Records contain demo_id and explicitly namespaced identity/duplicate tokens.

    Callers must not pass anonymous player slots as verified player tokens.
    Unknown identities remain an explicit limitation of the resulting evaluation.
    """
    ids = [str(r["demo_id"]) for r in records]
    if len(ids) != len(set(ids)) or not all(ids):
        raise ValueError("Demo IDs must be nonempty and unique")
    parent = {d: d for d in ids}

    def root(d):
        while parent[d] != d:
            parent[d] = parent[parent[d]]
            d = parent[d]
        return d

    owner = {}
    for record in records:
        d = str(record["demo_id"])
        for token in record.get("tokens", []):
            if not isinstance(token, str) or ":" not in token or not token.split(":", 1)[1]:
                raise ValueError("Identity tokens must be nonempty and namespaced")
            if token in owner:
                a, b = sorted((root(d), root(owner[token])))
                parent[b] = a
            else:
                owner[token] = d
    members = {}
    for d in ids:
        members.setdefault(root(d), []).append(d)
    hashes = {r: hashlib.sha256("\n".join(sorted(ds)).encode()).hexdigest() for r, ds in members.items()}
    return {d: hashes[root(d)] for d in sorted(ids)}


def assert_disjoint_groups(parts: dict[str, list[str]], groups: dict[str, str]) -> None:
    seen = set()
    for name, demos in parts.items():
        if not demos or len(demos) != len(set(demos)):
            raise ValueError(f"Empty or duplicate membership in {name}")
        current = {groups[d] for d in demos}
        if current & seen:
            raise ValueError(f"Group leakage into {name}")
        seen |= current


def nested_plan(groups: dict[str, str], *, outer_folds: int = 5, stack_folds: int = 4) -> list[dict]:
    """Entire matches split before model-specific eligibility filters.

    Calibration is one of five group folds of outer development data. Assignment
    uses group size only, never outcomes. All windows inherit their demo split.
    """
    demos = pd.Series(sorted(groups), dtype=str)
    labels = demos.map(groups)
    result = []
    for fold, (train_idx, test_idx) in enumerate(GroupKFold(outer_folds).split(demos, groups=labels)):
        available = demos.iloc[train_idx].reset_index(drop=True)
        dev_idx, cal_idx = next(GroupKFold(5).split(available, groups=available.map(groups)))
        development = available.iloc[dev_idx].reset_index(drop=True)
        parts = dict(development=development.tolist(), calibration=available.iloc[cal_idx].tolist(), test=demos.iloc[test_idx].tolist())
        assert_disjoint_groups(parts, groups)
        inner = []
        for fit_idx, hold_idx in GroupKFold(stack_folds).split(development, groups=development.map(groups)):
            membership = dict(fit=development.iloc[fit_idx].tolist(), heldout=development.iloc[hold_idx].tolist())
            assert_disjoint_groups(membership, groups)
            inner.append(membership)
        result.append(dict(fold=fold, **parts, cnn_crossfit=inner))
    return result
