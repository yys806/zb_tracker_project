#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

ENDPOINT="http://127.0.0.1:9000/api/tracking-runs"
DRY_RUN=0
LOGS_DIR="$PROJECT_ROOT/logs"
RUN_DIR=""
BENCHMARK_JSON="$PROJECT_ROOT/benchmark_results/morphology_benchmark.json"

while [ $# -gt 0 ]; do
  case "$1" in
    --endpoint)
      ENDPOINT="${2:-$ENDPOINT}"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --logs-dir)
      LOGS_DIR="${2:-$LOGS_DIR}"
      shift 2
      ;;
    --run-dir)
      RUN_DIR="${2:-}"
      shift 2
      ;;
    --benchmark-json)
      BENCHMARK_JSON="${2:-$BENCHMARK_JSON}"
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
echo "[08] upload latest summary"
echo "[08] endpoint: $ENDPOINT"
if [ "$DRY_RUN" -eq 1 ]; then
  echo "[08] dry-run"
fi

ARGS=(--endpoint "$ENDPOINT" --logs-dir "$LOGS_DIR" --benchmark-json "$BENCHMARK_JSON")
if [ -n "$RUN_DIR" ]; then
  ARGS+=(--run-dir "$RUN_DIR")
fi
if [ "$DRY_RUN" -eq 1 ]; then
  ARGS+=(--dry-run)
fi

PYTHONPATH=src "$PYTHON_BIN" scripts/upload_latest_summary.py "${ARGS[@]}"
