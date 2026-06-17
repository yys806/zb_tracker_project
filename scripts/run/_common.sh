#!/usr/bin/env bash
set -euo pipefail

RUN_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$RUN_SCRIPT_DIR/../.." && pwd)"
VENV_ROOT="${VENV_ROOT:-$HOME/.venvs/zb}"
PYTHON_BIN="${PYTHON_BIN:-$VENV_ROOT/bin/python}"
PIP_BIN="${PIP_BIN:-$VENV_ROOT/bin/pip}"

load_local_env() {
  local env_file="$PROJECT_ROOT/.env.local"
  if [ -f "$env_file" ]; then
    local clean_env_file
    clean_env_file="$(mktemp)"
    tr -d '\r' < "$env_file" > "$clean_env_file"
    set -a
    # shellcheck disable=SC1090
    source "$clean_env_file"
    set +a
    rm -f "$clean_env_file"
  fi
}

sudo_env_args() {
  local args=("PYTHONPATH=src")
  if [ -n "${DEEPSEEK_API_KEY:-}" ]; then
    args+=("DEEPSEEK_API_KEY=$DEEPSEEK_API_KEY")
  fi
  if [ -n "${DEEPSEEK_API_BASE:-}" ]; then
    args+=("DEEPSEEK_API_BASE=$DEEPSEEK_API_BASE")
  fi
  if [ -n "${DEEPSEEK_MODEL:-}" ]; then
    args+=("DEEPSEEK_MODEL=$DEEPSEEK_MODEL")
  fi
  printf '%s\n' "${args[@]}"
}

load_local_env

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

stop_existing_web_server() {
  local port="${1:-5000}"
  echo "[common] stopping old web console process if it exists"
  pkill -f "main.py --mode web" 2>/dev/null || true
  if command -v sudo >/dev/null 2>&1; then
    sudo pkill -f "main.py --mode web" 2>/dev/null || true
  fi
  if command -v fuser >/dev/null 2>&1; then
    fuser -k "${port}/tcp" 2>/dev/null || true
    if command -v sudo >/dev/null 2>&1; then
      sudo fuser -k "${port}/tcp" 2>/dev/null || true
    fi
  fi
  sleep 0.5
}
