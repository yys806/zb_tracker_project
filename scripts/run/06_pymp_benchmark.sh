#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

FRAMES=60
WIDTH=160
HEIGHT=120

while [ $# -gt 0 ]; do
  case "$1" in
    --frames)
      FRAMES="${2:-60}"
      shift 2
      ;;
    --width)
      WIDTH="${2:-160}"
      shift 2
      ;;
    --height)
      HEIGHT="${2:-120}"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1"
      exit 1
      ;;
  esac
done

cd "$PROJECT_ROOT"
ensure_output_dirs
echo "[06] pymp benchmark"
PYTHONPATH=src "$PYTHON_BIN" scripts/benchmark_morphology.py --config configs/default_config.json --frames "$FRAMES" --width "$WIDTH" --height "$HEIGHT" --skip-python --include-pymp
