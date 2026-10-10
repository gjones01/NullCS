"""Environment-file paths must agree with shared artifact/evidence loaders."""
import os
import subprocess
import sys
from pathlib import Path


def test_dotenv_is_loaded_before_shared_paths(tmp_path):
    repo = Path(__file__).resolve().parents[4]
    script = '''
import os, sys
from pathlib import Path
import dotenv
target = Path(sys.argv[1])
os.environ.pop('CLARITY_PROCESSED_DIR', None)
os.environ.pop('NULLCS_UPLOAD_DIR', None)
original_exists = Path.exists
Path.exists = lambda self: self.name == '.env' or original_exists(self)
def simulated_env_file(*args, **kwargs):
    os.environ['CLARITY_PROCESSED_DIR'] = str(target / 'processed')
    os.environ['NULLCS_UPLOAD_DIR'] = str(target / 'uploads')
dotenv.load_dotenv = simulated_env_file
from main.ui.api import config
from main.src.utils import project_paths
assert config.PROCESSED_DIR == project_paths.PROCESSED_ROOT == target / 'processed'
assert config.UPLOAD_DIR == project_paths.RAW_UPLOADS_ROOT == target / 'uploads'
'''
    env = {**os.environ, 'CLARITY_PYTHON_EXE': sys.executable, 'NULLCS_PROJECT_ROOT': str(repo)}
    result = subprocess.run([sys.executable, '-B', '-c', script, str(tmp_path)], cwd=repo, env=env, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
