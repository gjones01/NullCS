from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]  # .../main
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.adapters import demoparser2_local as d2l
from src.utils.project_paths import DEMOS_ROOT, RAW_UPLOADS_ROOT


# Sentinel demo: 232 MB upload recorded under CS2 patch 14153, the patch that dropped 53
# sendtable fields (including CCSPlayer_WeaponServices.m_bIsLookingAtWeapon). It is the
# fixture that answers "what did demoparser2 actually expose on a known patch" without
# re-deriving it from memory, so the answer is recorded in a pin next to its artifacts.
PINNED_DEMO_ID = "TEST_20260501_102349_02b8afde"

# Tick props demoparser2 only emits when they were updated inside the parsed range:
# a single-tick probe reports velocity_X/Y/Z as missing at tick 1000 (freeze time, no
# movement), so the fast probe always covers a real gameplay window instead.
DEFAULT_WINDOW_OFFSET = 64
DEFAULT_WINDOW_TICKS = 256

EXIT_OK = 0
EXIT_CONTRACT_DRIFT = 1
EXIT_DEMO_MISSING = 2


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description=(
            "Probe the demoparser2 tick contract on a pinned demo and compare it with a recorded "
            "pin. CS2 sendtable churn removes props silently, so a demoparser2 release or CS2 patch "
            "that drops a model input would otherwise only show up as a changed score."
        )
    )
    ap.add_argument("--demo_id", default=PINNED_DEMO_ID, help="Pinned demo id (default: the patch-14153 sentinel).")
    ap.add_argument("--dem_path", default=None, help="Explicit .dem path instead of resolving it from the demo id.")
    ap.add_argument("--pin", default=None, help="Pin JSON path (default: demos/<demo_id>/parser_contract_pin.json).")
    ap.add_argument("--write-pin", action="store_true", help="Record the observed contract as the new pin.")
    ap.add_argument("--window-start", type=int, default=None, help="First tick of the fast probe window.")
    ap.add_argument("--window-ticks", type=int, default=DEFAULT_WINDOW_TICKS, help="Probe window length in ticks.")
    ap.add_argument("--skip-full", action="store_true", help="Skip the full-demo production parse.")
    ap.add_argument("--json-out", default=None, help="Optional path for the JSON report.")
    return ap.parse_args()


def resolve_demo_path(demo_id: str, dem_path: str | None) -> tuple[Path, str]:
    if dem_path:
        path = Path(dem_path)
        if not path.exists():
            raise FileNotFoundError(f"Demo file not found: {path}")
        return path, "explicit --dem_path"

    upload = Path(RAW_UPLOADS_ROOT) / demo_id / f"{demo_id}.dem"
    if upload.exists():
        return upload, "raw upload"

    meta_path = Path(DEMOS_ROOT) / demo_id / "meta.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8-sig"))
        source = Path(str(meta.get("source_demo", "")).strip())
        if str(meta.get("source_demo", "")).strip() and source.exists():
            return source, "meta.json source_demo"

    raise FileNotFoundError(
        f"Cannot resolve a .dem for demo_id '{demo_id}'. Looked for {upload} and "
        f"{meta_path}. Pass --dem_path to check another demo."
    )


def probe_window_start(round_starts: list[int], explicit_start: int | None) -> int:
    if explicit_start is not None:
        return int(explicit_start)
    if len(round_starts) >= 4:
        # The 4th round start is past warm-up/knife-round churn; +offset clears freeze time.
        return int(round_starts[3]) + DEFAULT_WINDOW_OFFSET
    if round_starts:
        return int(round_starts[0]) + DEFAULT_WINDOW_OFFSET
    return DEFAULT_WINDOW_OFFSET


def classify(present: set[str]) -> dict[str, list[str]]:
    return {
        "missing_critical": sorted(d2l.CRITICAL_TICK_COLUMNS.difference(present)),
        "missing_model": sorted(d2l.MODEL_TICK_COLUMNS.difference(present)),
        "missing_decorative": sorted(col for col in d2l.DECORATIVE_TICK_COLUMNS if col not in present),
        "present_model": sorted(d2l.MODEL_TICK_COLUMNS.intersection(present)),
    }


def read_pin(path: Path) -> dict | None:
    """Read a pin, tolerating the BOM that Windows editors/tools add (utf-8-sig)."""
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    return payload if isinstance(payload, dict) else None


def pin_contract(pin: dict) -> dict[str, list[str]]:
    window = pin.get("window") if isinstance(pin.get("window"), dict) else {}
    return {
        "missing_critical": list(window.get("missing_critical", [])),
        "missing_model": list(window.get("missing_model", [])),
        "missing_decorative": list(window.get("missing_decorative", [])),
        "present_model": list(window.get("present_model", [])),
    }


def diff_contract(expected: dict[str, list[str]], observed: dict[str, list[str]]) -> dict[str, dict[str, list[str]]]:
    drift: dict[str, dict[str, list[str]]] = {}
    for key in sorted(set(expected) | set(observed)):
        before = sorted(str(x) for x in expected.get(key, []))
        after = sorted(str(x) for x in observed.get(key, []))
        if before != after:
            drift[key] = {"pin": before, "now": after}
    return drift


def main() -> int:
    args = parse_args()
    demo_id = str(args.demo_id).strip()
    pin_path = Path(args.pin) if args.pin else Path(DEMOS_ROOT) / demo_id / "parser_contract_pin.json"

    try:
        dem_path, resolution = resolve_demo_path(demo_id, args.dem_path)
    except FileNotFoundError as exc:
        print(f"[FAIL] {exc}")
        print("[INFO] This check needs the pinned .dem on disk; main/data/** is gitignored, so it cannot run from a bare clone.")
        return EXIT_DEMO_MISSING
    print(f"[INFO] demo: {dem_path} ({resolution})")

    parser = d2l.DemoParser(str(dem_path))
    header = parser.parse_header()
    provenance = d2l.parser_provenance(header)
    print(
        "[INFO] provenance: "
        f"patch_version={provenance.get('patch_version', 'unknown')} "
        f"demo_version={provenance.get('demo_version_name', 'unknown')} "
        f"map={provenance.get('map_name', 'unknown')} "
        f"demoparser2={provenance.get('demoparser2_version', 'unknown')}"
    )

    freeze = d2l._safe_event(parser, "round_freeze_end")
    round_starts = sorted(int(x) for x in freeze.get("tick", pd.Series(dtype="int64")).dropna().tolist())
    window_start = probe_window_start(round_starts, args.window_start)
    window_ticks = max(1, int(args.window_ticks))
    requested = ["tick", "steamid", *d2l.WANTED_TICK_PROPS]
    window_df = parser.parse_ticks(requested, ticks=list(range(window_start, window_start + window_ticks)))
    window_present = set(window_df.columns)
    window_classification = classify(window_present)
    print(
        f"[INFO] window probe: start={window_start} ticks={window_ticks} rows={len(window_df)} "
        f"rounds_parsed={len(round_starts)}"
    )

    full_report: dict[str, object] = {"rows": None, "columns": None, "error": None}
    if args.skip_full:
        print("[INFO] full-demo production parse skipped (--skip-full)")
    else:
        try:
            full_df = d2l._ticks_table(parser)
            full_report = {"rows": int(len(full_df)), "columns": int(len(full_df.columns)), "error": None}
            print(f"[INFO] full demo parse through _ticks_table: rows={full_report['rows']} columns={full_report['columns']}")
        except Exception as exc:
            full_report = {"rows": None, "columns": None, "error": f"{type(exc).__name__}: {exc}"}
            print(f"[FAIL] production tick guard rejected this demo: {full_report['error']}")

    observed = dict(window_classification)
    if window_classification["missing_critical"]:
        print(f"[FAIL] window probe is missing critical tick columns: {window_classification['missing_critical']}")
    if window_classification["missing_model"]:
        print(f"[FAIL] window probe is missing model-input columns: {window_classification['missing_model']}")
    if window_classification["missing_decorative"]:
        print(
            "[WARN] window probe is missing decorative tick columns: "
            f"{window_classification['missing_decorative']} (zero-filled, not model inputs)"
        )

    pin: dict | None = None
    pin_error: str | None = None
    try:
        pin = read_pin(pin_path)
    except Exception as exc:
        # An unreadable pin must not be mistaken for "no pin yet": that would turn a broken
        # drift check into a silent pass.
        pin_error = f"{type(exc).__name__}: {exc}"
        print(f"[FAIL] pin {pin_path} is unreadable: {pin_error}")
    drift: dict[str, dict[str, list[str]]] = {}
    if pin_error:
        pass
    elif pin is None:
        print(f"[WARN] no pin at {pin_path}; run with --write-pin to record the observed contract")
    else:
        pin_patch = str(pin.get("patch_version", "")).strip()
        observed_patch = str(provenance.get("patch_version", "")).strip()
        if pin_patch and observed_patch and pin_patch != observed_patch:
            drift["patch_version"] = {"pin": [pin_patch], "now": [observed_patch]}
        pin_parser = str(pin.get("demoparser2_version", "")).strip()
        observed_parser = str(provenance.get("demoparser2_version", "")).strip()
        if pin_parser and observed_parser and pin_parser != observed_parser:
            print(f"[INFO] demoparser2 version changed since the pin was recorded: {pin_parser} -> {observed_parser}")
        drift.update(diff_contract(pin_contract(pin), observed))
        if drift:
            print("[FAIL] parser contract drifted from the pin:")
            for key, change in drift.items():
                print(f"       {key}: pin={change['pin']} now={change['now']}")
        else:
            print(f"[OK] parser contract matches the pin ({pin_path})")

    verdict = "ok"
    if window_classification["missing_critical"] or window_classification["missing_model"]:
        verdict = "missing_model_columns"
    elif full_report["error"]:
        verdict = "production_guard_rejected_demo"
    elif pin_error:
        verdict = "unreadable_pin"
    elif drift and not args.write_pin:
        verdict = "drift"

    report = {
        "demo_id": demo_id,
        "demo_file": str(dem_path),
        "provenance": provenance,
        "window": {"start": window_start, "ticks": window_ticks, "rows": int(len(window_df)), **window_classification},
        "full_parse": full_report,
        "pin": {"path": str(pin_path), "found": pin is not None, "error": pin_error, "drift": drift},
        "verdict": verdict,
    }

    if args.write_pin:
        pin_payload = {
            "demo_id": demo_id,
            "demo_file": str(dem_path),
            "recorded_at": dt.datetime.now().isoformat(timespec="seconds"),
            **provenance,
            "window": {"start": window_start, "ticks": window_ticks, "rows": int(len(window_df)), **window_classification},
            "full_parse": full_report,
        }
        pin_path.parent.mkdir(parents=True, exist_ok=True)
        pin_path.write_text(json.dumps(pin_payload, indent=2), encoding="utf-8")
        print(f"[OK] wrote pin {pin_path}")
        if verdict in {"drift", "unreadable_pin"}:
            verdict = "ok"
            report["verdict"] = verdict
            report["pin"]["drift"] = {}
            report["pin"]["found"] = True
            report["pin"]["error"] = None

    if args.json_out:
        json_out = Path(args.json_out)
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"[OK] wrote {json_out}")

    if verdict == "ok":
        print("[OK] parser contract check passed")
        return EXIT_OK
    print(f"[FAIL] parser contract check failed ({verdict})")
    if verdict != "unreadable_pin":
        print(
            "[INFO] a dropped critical/model column means the installed demoparser2 build no longer matches "
            "the feature contract for this patch; confirm the prop names before scoring any demo with it."
        )
    return EXIT_CONTRACT_DRIFT


if __name__ == "__main__":
    raise SystemExit(main())