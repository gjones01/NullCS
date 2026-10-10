import os
import subprocess
import sys
from pathlib import Path

from main.ui.api.pipeline_runtime import run_process

WRAPPER = Path(__file__).resolve().parents[1] / 'pipeline_child.py'


def test_watchdog_allows_model_imports_and_normal_exit(tmp_path):
    script = tmp_path / 'imports.py'
    script.write_text("import numpy, pandas, xgboost, torch; print('model imports completed', flush=True)")
    run_process([sys.executable, '-u', str(WRAPPER), str(script)], cwd=tmp_path,
                env=dict(os.environ), log=tmp_path/'imports.log', timeout=30, on_stage=lambda _: None)
    assert 'model imports completed' in (tmp_path/'imports.log').read_text()


def test_watchdog_exits_when_parent_pipe_closes(tmp_path):
    script = tmp_path / 'waiting.py'
    script.write_text("import time; print('ready', flush=True); time.sleep(60)")
    child = subprocess.Popen([sys.executable, '-u', str(WRAPPER), str(script)], stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        assert child.stdout.readline().strip() == b'ready'
        child.stdin.close()
        assert child.wait(timeout=5) == 75
    finally:
        if child.poll() is None:
            child.kill()
        child.wait()
        child.stdout.close()
