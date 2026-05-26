from __future__ import annotations

import re

import polars as pl


def _split_steamids(raw: str) -> list[str]:
    parts = re.split(r"[;,|\s]+", str(raw).strip())
    return [p.strip() for p in parts if p and p.strip()]


def load_cheater_map(csv_path) -> dict[str, set[str]]:
    import pandas as pd

    if not csv_path.exists():
        return {}

    df = pd.read_csv(csv_path, dtype=str)
    cols = {c.lower().strip(): c for c in df.columns}
    demo_col = cols.get("cdemo id") or cols.get("demo id") or cols.get("demo_id") or cols.get("cdemo")
    id_col = cols.get("name/id") or cols.get("steamid") or cols.get("steam_id") or cols.get("id")
    id_cols: list[str] = []
    if id_col is not None:
        id_cols.append(id_col)
    for lc, orig in cols.items():
        if lc.startswith("steamid") or lc.startswith("steam_id") or lc.startswith("cheater_steamid"):
            if orig not in id_cols:
                id_cols.append(orig)
    if demo_col is None or not id_cols:
        raise ValueError(f"Cheater CSV must have demo+steamid columns. Found: {list(df.columns)}")

    df = df[[demo_col, *id_cols]].copy()
    df = df.rename(columns={demo_col: "demo_id"})
    df["demo_id"] = df["demo_id"].astype(str).str.strip()
    df = df[df["demo_id"] != ""]

    exploded = []
    for _, row in df.iterrows():
        demo_id = str(row["demo_id"]).strip()
        for col in id_cols:
            for sid in _split_steamids(row[col]):
                exploded.append((demo_id, sid))
    if not exploded:
        return {}
    edf = pd.DataFrame(exploded, columns=["demo_id", "cheater_steamid"]).drop_duplicates()
    return edf.groupby("demo_id")["cheater_steamid"].apply(set).to_dict()


def demo_base_label(demo_id: str) -> int | None:
    d = str(demo_id).lower()
    if d.startswith("pro") or d.startswith("normal"):
        return 0
    if d.startswith("cdemo"):
        return None
    return None


def label_demo_frame_pl(
    df: pl.DataFrame,
    demo_id: str,
    source: str,
    cheater_map: dict[str, set[str]],
) -> pl.DataFrame | None:
    if df.is_empty():
        return None
    if "attacker_steamid" not in df.columns:
        return None

    base = demo_base_label(demo_id)
    is_cd = demo_id.lower().startswith("cdemo")
    sid_expr = pl.col("attacker_steamid").cast(pl.Utf8).str.strip_chars()
    out = df.with_columns(
        pl.lit(demo_id).alias("demo_id"),
        pl.lit(source).alias("dataset_source"),
        sid_expr.alias("attacker_steamid"),
    )

    has_inline_label = "label" in out.columns and out["label"].drop_nulls().len() > 0
    if has_inline_label:
        out = out.with_columns(pl.col("label").cast(pl.Float64, strict=False).fill_null(0).cast(pl.Int64))
    elif is_cd:
        cheater_ids = cheater_map.get(demo_id)
        if not cheater_ids:
            return None
        out = out.with_columns(pl.col("attacker_steamid").is_in(sorted(cheater_ids)).cast(pl.Int64).alias("label"))
    else:
        if base is None:
            return None
        out = out.with_columns(pl.lit(int(base)).alias("label"))

    if "attacker_name" not in out.columns:
        out = out.with_columns(pl.lit("").alias("attacker_name"))
    if "map_name" not in out.columns:
        out = out.with_columns(pl.lit("").alias("map_name"))
    return out


def ensure_columns_pl(df: pl.DataFrame, defaults: list[tuple[str, object]]) -> pl.DataFrame:
    exprs: list[pl.Expr] = []
    for col, default in defaults:
        if col in df.columns:
            continue
        exprs.append(pl.lit(default).alias(col))
    return df.with_columns(exprs) if exprs else df
