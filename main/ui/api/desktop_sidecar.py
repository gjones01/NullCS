from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _bootstrap_paths() -> None:
    project_root = Path(os.getenv("NULLCS_PROJECT_ROOT", "")).resolve() if os.getenv("NULLCS_PROJECT_ROOT") else None
    candidates = []
    if project_root:
        candidates.extend([project_root, project_root / "main"])
    candidates.extend([Path(__file__).resolve().parents[3], Path(__file__).resolve().parents[2]])
    for path in candidates:
        text = str(path)
        if path.exists() and text not in sys.path:
            sys.path.insert(0, text)


def _run_module_main(module_name: str, argv: list[str]) -> int:
    _bootstrap_paths()
    sys.argv = [module_name, *argv]
    module = __import__(module_name, fromlist=["main"])
    result = module.main()
    return int(result or 0)


def _run_api(host: str, port: int) -> int:
    _bootstrap_paths()
    import uvicorn

    uvicorn.run(
        "main.ui.api.main:app",
        host=host,
        port=port,
        log_level="info",
        access_log=False,
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="NullCS packaged desktop backend sidecar.")
    sub = parser.add_subparsers(dest="mode", required=True)

    api = sub.add_parser("api", help="Start the local authenticated API server.")
    api.add_argument("--host", default="127.0.0.1")
    api.add_argument("--port", type=int, required=True)

    run_infer = sub.add_parser("run-infer", help="Run one-demo inference.")
    run_infer.add_argument("args", nargs=argparse.REMAINDER)

    explain = sub.add_parser("explain", help="Generate a player explanation report.")
    explain.add_argument("args", nargs=argparse.REMAINDER)

    args = parser.parse_args()
    if args.mode == "api":
        return _run_api(args.host, args.port)
    if args.mode == "run-infer":
        return _run_module_main("main.scripts.run_infer_pipeline", args.args)
    if args.mode == "explain":
        return _run_module_main("main.scripts.explain_demo", args.args)
    parser.error("Unknown mode")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
