#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

BACKEND="${1:-cpp}"

cd "$PROJECT_ROOT"
ensure_output_dirs
echo "[10] backend: $BACKEND"
PYTHONPATH=src "$PYTHON_BIN" main.py --mode web --simulate --tracker-backend "$BACKEND" --web-jpeg-quality 60 --web-fps 10
