from __future__ import annotations

from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAIN_ROOT = PROJECT_ROOT / "main"
if str(MAIN_ROOT) not in sys.path:
    sys.path.insert(0, str(MAIN_ROOT))

from src.utils.project_paths import newanubis_venv_python


PY = newanubis_venv_python(PROJECT_ROOT)
PARSE_SCRIPT = PROJECT_ROOT / "main" / "src" / "parse" / "parse_demos_awpy_api.py"
FEATURES_SCRIPT = PROJECT_ROOT / "main" / "src" / "features" / "build_engagement_features.py"
AGGREGATE_SCRIPT = PROJECT_ROOT / "main" / "src" / "features" / "aggregate_player_features.py"
TRAIN_SCRIPT = PROJECT_ROOT / "main" / "scripts" / "train_xgb_gridcv.py"
EVAL_SCRIPT = PROJECT_ROOT / "main" / "scripts" / "evaluate_xgb_gridcv.py"


def run_step(label: str, script: Path) -> None:
    if not script.exists():
        raise FileNotFoundError(f"{label} script not found: {script}")

    print(f"\n=== {label} ===")
    cmd = [str(PY), str(script)]
    print("[RUN]", " ".join(cmd))

    p = subprocess.run(cmd)
    if p.returncode != 0:
        raise RuntimeError(f"{label} failed with exit code {p.returncode}")


def main():
    run_step("PARSE DEMOS", PARSE_SCRIPT)
    run_step("BUILD ENGAGEMENT + ENCOUNTER FEATURES", FEATURES_SCRIPT)
    run_step("AGGREGATE PLAYER FEATURES", AGGREGATE_SCRIPT)
    run_step("TRAIN MODEL", TRAIN_SCRIPT)
    run_step("EVALUATE MODEL", EVAL_SCRIPT)
    print("\nPipeline complete.")


if __name__ == "__main__":
    main()
