from __future__ import annotations

import argparse
import json
import os
import re
import sys
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.adapters.demoparser2_local import load_demo as load_demoparser2_demo
from src.features.build_cs2cd_engagement_features import build_match_outputs
from src.utils.project_paths import DEMOS_ROOT, LEGIT_PRO_RENAMED_ROOT


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Ingest extra pro legit demos through the demoparser2 -> CS2CD feature path.")
    ap.add_argument("--workers", type=int, default=2, help="Parallel worker processes. Keep modest to preserve desktop usability.")
    ap.add_argument("--overwrite", action="store_true", help="Overwrite existing processed outputs for these pro demos.")
    ap.add_argument("--max-demos", type=int, default=None, help="Optional cap for quick validation.")
    return ap.parse_args()


def _safe_token(text: str) -> str:
    token = re.sub(r"[^A-Za-z0-9]+", "_", str(text).strip())
    token = re.sub(r"_+", "_", token).strip("_")
    return token or "UNKNOWN"


def _demo_id_for_file(path: Path) -> str:
    return f"CS2CD_PROLEGIT_{_safe_token(path.stem)}"


def _output_paths(demo_id: str) -> tuple[Path, Path, Path, Path]:
    demo_dir = DEMOS_ROOT / demo_id
    return (
        demo_dir,
        demo_dir / "engagement_features.parquet",
        demo_dir / "encounters.parquet",
        demo_dir / "meta.json",
    )


def _process_one_demo(demo_path: str, overwrite: bool) -> tuple[str, str, str | None]:
    src = Path(demo_path)
    demo_id = _demo_id_for_file(src)
    demo_dir, kill_out, enc_out, meta_out = _output_paths(demo_id)
    try:
        if kill_out.exists() and enc_out.exists() and not overwrite:
            return "skipped", demo_id, None

        match = load_demoparser2_demo(src, demo_id=demo_id)
        kill_rows, encounter_rows = build_match_outputs(match)
        if kill_rows.empty:
            return "skipped", demo_id, "empty kill rows"

        demo_dir.mkdir(parents=True, exist_ok=True)
        kill_rows.to_parquet(kill_out, index=False)
        encounter_rows.to_parquet(enc_out, index=False)
        meta = {
            "demo_id": demo_id,
            "source_demo": str(src),
            "source_type": "legit_pro_renamed",
            "map_name": match.map_name,
            "n_kills": int(len(kill_rows)),
            "n_encounters": int(len(encounter_rows)),
            "n_cheaters_annotated": 0,
        }
        meta_out.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        return "built", demo_id, None
    except Exception as exc:
        err = "".join(traceback.format_exception_only(type(exc), exc)).strip()
        return "failed", demo_id, err


def main() -> int:
    args = parse_args()
    demo_paths = sorted(LEGIT_PRO_RENAMED_ROOT.glob("*.dem"))
    if args.max_demos is not None:
        demo_paths = demo_paths[: args.max_demos]
    if not demo_paths:
        raise FileNotFoundError(f"No .dem files found under {LEGIT_PRO_RENAMED_ROOT}")

    built = 0
    skipped = 0
    failed = 0

    workers = max(1, min(int(args.workers), os.cpu_count() or 1))
    print(f"[INFO] pro demos total={len(demo_paths)} workers={workers} overwrite={bool(args.overwrite)}")

    if workers <= 1:
        for idx, path in enumerate(demo_paths, start=1):
            status, demo_id, err = _process_one_demo(str(path), args.overwrite)
            if status == "built":
                built += 1
                print(f"[BUILD {idx}/{len(demo_paths)}] {demo_id}")
            elif status == "skipped":
                skipped += 1
                print(f"[SKIP {idx}/{len(demo_paths)}] {demo_id} {f'({err})' if err else ''}".rstrip())
            else:
                failed += 1
                print(f"[FAIL {idx}/{len(demo_paths)}] {demo_id}: {err}")
        print(f"[OK] pro legit ingest complete. built={built} skipped={skipped} failed={failed}")
        return 0 if failed == 0 else 2

    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_process_one_demo, str(path), bool(args.overwrite)): path for path in demo_paths}
        done_n = 0
        for fut in as_completed(futs):
            done_n += 1
            status, demo_id, err = fut.result()
            if status == "built":
                built += 1
                print(f"[BUILD {done_n}/{len(demo_paths)}] {demo_id}")
            elif status == "skipped":
                skipped += 1
                print(f"[SKIP {done_n}/{len(demo_paths)}] {demo_id} {f'({err})' if err else ''}".rstrip())
            else:
                failed += 1
                print(f"[FAIL {done_n}/{len(demo_paths)}] {demo_id}: {err}")

    print(f"[OK] pro legit ingest complete. built={built} skipped={skipped} failed={failed}")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
