#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
backend_cmd="python -m uvicorn main.ui.api.main:app --host 127.0.0.1 --port 8000 --reload"
frontend_cmd="npm run dev -- --host 0.0.0.0 --port 5173"

echo "NullCS dev commands:"
echo "  Backend : $backend_cmd"
echo "  Frontend: $frontend_cmd"
echo
echo "Run from:"
echo "  Backend : $repo_root"
echo "  Frontend: $repo_root/main/ui/web"
