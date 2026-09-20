from __future__ import annotations

from pathlib import Path


def write_df_to_parquet(df, path: Path) -> None:
    """Write a polars dataframe to parquet.

    Shared by the parse and single-demo inference paths, which had identical
    copies of this one-liner (AUDIT.md finding F10).
    """
    df.write_parquet(str(path))