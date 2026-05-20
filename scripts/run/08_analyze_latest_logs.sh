#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

cd "$PROJECT_ROOT"
ensure_output_dirs
echo "[08] analyze latest logs"
PYTHONPATH=src "$PYTHON_BIN" scripts/analyze_tracking_logs.py
