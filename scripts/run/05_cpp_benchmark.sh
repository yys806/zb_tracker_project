#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

FRAMES=10
WIDTH=80
HEIGHT=60
BENCH_ARGS=()

while [ $# -gt 0 ]; do
  case "$1" in
    --frames)
      FRAMES="${2:-10}"
      shift 2
      ;;
    --width)
      WIDTH="${2:-80}"
      shift 2
      ;;
    --height)
      HEIGHT="${2:-60}"
      shift 2
      ;;
    *)
      BENCH_ARGS+=("$1")
      shift
      ;;
  esac
done

cd "$PROJECT_ROOT/cpp_accel"
echo "[05] clean old build"
sudo rm -rf build dist morphology_ext.egg-info
sudo chown -R "$(id -u):$(id -g)" .
echo "[05] build wheel"
"$PYTHON_BIN" setup.py bdist_wheel
echo "[05] install wheel"
"$PIP_BIN" install dist/*.whl --force-reinstall --no-deps
echo "[05] verify module"
"$PYTHON_BIN" -c "import morphology_ext; print(morphology_ext.__doc__)"
cd "$PROJECT_ROOT"
echo "[05] run benchmark"
PYTHONPATH=src "$PYTHON_BIN" scripts/benchmark_morphology.py --config configs/default_config.json --frames "$FRAMES" --width "$WIDTH" --height "$HEIGHT" --include-pymp "${BENCH_ARGS[@]}"
