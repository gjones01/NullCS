from __future__ import annotations


def safe_print(text: str) -> None:
    """Print text, degrading to ASCII when the console cannot encode it.

    Consolidates the identical ``safe_print`` / ``_safe_print`` helpers that
    were copied into the aggregation, explain, inference and benchmark scripts
    (AUDIT.md finding F10).
    """
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"))