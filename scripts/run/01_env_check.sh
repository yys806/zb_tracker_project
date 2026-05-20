#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

cd "$PROJECT_ROOT"
ensure_output_dirs
echo "[01] install deps"
"$PIP_BIN" install -r requirements.txt
"$PIP_BIN" install smbus2
echo "[01] verify deps"
"$PYTHON_BIN" -c "import cv2, smbus2; print('opencv and smbus2 ok')"
echo "[01] verify package"
PYTHONPATH=src "$PYTHON_BIN" -c "import orangepi_tracker; print(orangepi_tracker)"
echo "[01] run unit tests"
PYTHONPATH=src "$PYTHON_BIN" -m unittest discover -s tests -v
