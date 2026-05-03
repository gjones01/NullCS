from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient


def build_client(tmp_path: Path, **env_overrides: str) -> TestClient:
    env = {
        "NULLCS_ENV": "development",
        "NULLCS_DEMO_MODE": "0",
        "NULLCS_FRONTEND_ORIGIN": "http://localhost:5173",
        "NULLCS_UPLOAD_DIR": str(tmp_path / "uploads"),
        "CLARITY_PROCESSED_DIR": str(tmp_path / "processed"),
        "CLARITY_PROJECT_ROOT": str(tmp_path / "project"),
        "NULLCS_MAX_UPLOAD_BYTES": str(1024 * 1024),
    }
    env.update(env_overrides)
    for key, value in env.items():
        os.environ[key] = value

    for module_name in ["main.ui.api.main", "main.ui.api.config"]:
        sys.modules.pop(module_name, None)

    module = importlib.import_module("main.ui.api.main")
    return TestClient(module.app)


def test_health_reports_demo_mode(tmp_path: Path):
    client = build_client(tmp_path, NULLCS_DEMO_MODE="1")
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "demo"
    assert payload["upload_enabled"] is False


def test_upload_rejects_wrong_extension(tmp_path: Path):
    client = build_client(tmp_path)
    response = client.post(
        "/api/upload-demo",
        files={"file": ("not-a-demo.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 400
    assert response.json()["error"]["message"] == "Only .dem uploads are supported"


def test_upload_rejects_executable_magic(tmp_path: Path):
    client = build_client(tmp_path)
    response = client.post(
        "/api/upload-demo",
        files={"file": ("renamed.dem", b"MZfakepayload", "application/octet-stream")},
    )
    assert response.status_code == 400
    assert "not allowed" in response.json()["error"]["message"].lower()


def test_production_requires_api_key(tmp_path: Path):
    client = build_client(tmp_path, NULLCS_ENV="production", NULLCS_API_KEY="topsecret")
    response = client.post(
        "/api/upload-demo",
        files={"file": ("demo.dem", b"demo", "application/octet-stream")},
    )
    assert response.status_code == 401
    assert response.json()["error"]["message"] == "API key required"

    ok = client.post(
        "/api/upload-demo",
        headers={"X-NULLCS-KEY": "topsecret"},
        files={"file": ("demo.dem", b"demo", "application/octet-stream")},
    )
    assert ok.status_code == 200
