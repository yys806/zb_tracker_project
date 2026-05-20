#!/usr/bin/env bash
set -euo pipefail

RUN_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$RUN_SCRIPT_DIR/../.." && pwd)"
VENV_ROOT="${VENV_ROOT:-$HOME/.venvs/zb}"
PYTHON_BIN="${PYTHON_BIN:-$VENV_ROOT/bin/python}"
PIP_BIN="${PIP_BIN:-$VENV_ROOT/bin/pip}"

if [ ! -x "$PYTHON_BIN" ]; then
  echo "[common] cannot find virtualenv python: $PYTHON_BIN"
  echo "[common] creating virtualenv at $VENV_ROOT"
  mkdir -p "$(dirname "$VENV_ROOT")"
  if command -v python3 >/dev/null 2>&1; then
    python3 -m venv "$VENV_ROOT"
  else
    python -m venv "$VENV_ROOT"
  fi
fi

if [ ! -x "$PIP_BIN" ]; then
  echo "Cannot find virtualenv pip: $PIP_BIN"
  exit 1
fi

ensure_output_dirs() {
  cd "$PROJECT_ROOT"
  mkdir -p logs benchmark_results cloud_uploads
  for path in logs benchmark_results cloud_uploads; do
    if [ ! -w "$path" ]; then
      echo "[common] $path is not writable by $(id -un), trying sudo chown"
      sudo chown -R "$(id -u):$(id -g)" "$path"
    fi
  done
}
