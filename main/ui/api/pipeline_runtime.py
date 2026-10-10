"""Process boundary for web analysis. Research code remains in run_infer_pipeline."""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Callable

STAGES = ("preparing", "parsing", "feature_processing", "inference", "scoring")
STAGE_LABELS = {
    "upload_pending": "Waiting for upload", "uploading": "Uploading", "queued": "Queued",
    "preparing": "Preparing models", "parsing": "Parsing demo",
    "feature_processing": "Processing features", "inference": "Running temporal model",
    "scoring": "Scoring players", "results_ready": "Results ready", "failed": "Analysis failed",
}


class PipelineFailure(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def failure_from_log(text: str, stage: str) -> PipelineFailure:
    lower = text.lower()
    if "tick schema is missing" in lower:
        return PipelineFailure("parser_contract", "A required tick field is missing. This demo does not match the installed parser's model-input contract; no result was produced.")
    if any(x in lower for x in ("entitynotfound", "demoparser.exception", "unknowndemocmd", "illegalpathop")):
        return PipelineFailure("parser_failed", "The parser could not read this demo. It may be incomplete, corrupt, or from an unsupported CS2 version.")
    if "no space left" in lower or "disk full" in lower:
        return PipelineFailure("storage_failed", "The analysis worker ran out of storage. Please retry after service capacity is restored.")
    if any(x in lower for x in ("no model artifacts", "model artifact not found", "no feature list", "model expects encounter neural")) or ('traceback' in lower and any(x in lower for x in ('load_model', 'unpicklingerror', 'load_trained_encounter_model'))):
        return PipelineFailure("model_unavailable", "A required model or its supporting artifact could not be loaded. The service operator must check the worker configuration.")
    if "refusing to score" in lower or "feature_names mismatch" in lower or "leakage guardrail" in lower or "missing required inference support" in lower:
        return PipelineFailure("feature_contract", "The demo did not produce sufficient compatible model inputs. Analysis stopped without guessing a result.")
    if "calibrat" in lower and "traceback" in lower and stage == "scoring":
        return PipelineFailure("scoring_failed", "Scoring or calibration failed. No replacement calibrator or model was used.")
    return PipelineFailure("inference_failed", f"Analysis failed during {STAGE_LABELS.get(stage, 'processing').lower()}. Detailed diagnostics are available to the service operator.")


def run_process(cmd: list[str], *, cwd: Path, env: dict[str, str], log: Path,
                timeout: int, on_stage: Callable[[str], None], stopping=None) -> float:
    """Stream to a private log; only explicit pipeline events become public stages."""
    log.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    stage = "preparing"
    with log.open("w", encoding="utf-8") as out:
        try:
            proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=out, stderr=subprocess.STDOUT,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except OSError as exc:
            raise PipelineFailure("worker_start_failed", "The analysis process could not start. The service operator must check the worker runtime.") from exc
        try:
            while True:
                finished = proc.poll() is not None
                if stopping is not None and stopping.is_set():
                    raise PipelineFailure("worker_stopped", "The worker stopped before analysis completed. Please submit the demo again.")
                if time.monotonic() - started > timeout:
                    raise PipelineFailure("timeout", "Analysis exceeded the worker time limit. No completed result is available.")
                # Logs are small. No parser-dependent fake percentages or time-based stages.
                for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
                    if line.startswith("[NULLCS_STAGE] "):
                        candidate = line.split(" ", 1)[1].strip()
                        if candidate in STAGES and STAGES.index(candidate) > STAGES.index(stage):
                            stage = candidate
                            on_stage(stage)
                if finished:
                    break
                time.sleep(0.2)
            if proc.returncode:
                raise failure_from_log(log.read_text(encoding="utf-8", errors="replace"), stage)
        finally:
            if proc.poll() is None:
                proc.kill()
            proc.wait()
            if proc.stdin:
                proc.stdin.close()
    return time.monotonic() - started


def inference_command(settings, demo_id: str, source: Path) -> tuple[list[str], dict[str, str]]:
    cmd = ([settings.PIPELINE_EXE, "run-infer"] if settings.PIPELINE_EXE else
           [str(settings.PYTHON_EXE), "-u", str(Path(__file__).with_name('pipeline_child.py')), str(settings.SCRIPTS_DIR / "run_infer_pipeline.py")])
    cmd += ["--dem_path", str(source), "--demo_id", demo_id, "--out_dir", str(settings.PROCESSED_DIR)]
    if settings.MODEL_ARTIFACT:
        cmd += ["--model-artifact", settings.MODEL_ARTIFACT]
    env = dict(os.environ)
    env.update(NULLCS_UPLOAD_DIR=str(settings.UPLOAD_DIR),
               CLARITY_PROCESSED_DIR=str(settings.PROCESSED_DIR), PYTHONUNBUFFERED="1")
    return cmd, env
