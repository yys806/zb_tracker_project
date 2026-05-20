#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

HOST="127.0.0.1"
PORT="9000"
RUN_DIR=""
LOGS_DIR="$PROJECT_ROOT/logs"
BENCHMARK_JSON="$PROJECT_ROOT/benchmark_results/morphology_benchmark.json"

while [ $# -gt 0 ]; do
  case "$1" in
    --host)
      HOST="${2:-127.0.0.1}"
      shift 2
      ;;
    --port)
      PORT="${2:-9000}"
      shift 2
      ;;
    --run-dir)
      RUN_DIR="${2:-}"
      shift 2
      ;;
    --logs-dir)
      LOGS_DIR="${2:-$LOGS_DIR}"
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
ENDPOINT="http://$HOST:$PORT/api/tracking-runs"
echo "[12] start mock cloud"
PYTHONPATH=src "$PYTHON_BIN" scripts/mock_cloud_server.py --host "$HOST" --port "$PORT" > /tmp/mock_cloud_server.log 2>&1 &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null || true' EXIT
sleep 2

echo "[12] dry-run payload"
DRY_ARGS=(--logs-dir "$LOGS_DIR" --benchmark-json "$BENCHMARK_JSON" --dry-run)
if [ -n "$RUN_DIR" ]; then
  DRY_ARGS+=(--run-dir "$RUN_DIR")
fi
PYTHONPATH=src "$PYTHON_BIN" scripts/upload_latest_summary.py "${DRY_ARGS[@]}"

echo "[12] upload payload"
UPLOAD_ARGS=(--endpoint "$ENDPOINT" --logs-dir "$LOGS_DIR" --benchmark-json "$BENCHMARK_JSON")
if [ -n "$RUN_DIR" ]; then
  UPLOAD_ARGS+=(--run-dir "$RUN_DIR")
fi
PYTHONPATH=src "$PYTHON_BIN" scripts/upload_latest_summary.py "${UPLOAD_ARGS[@]}"

echo "[12] mock cloud log"
cat /tmp/mock_cloud_server.log
kill "$SERVER_PID"
wait "$SERVER_PID" 2>/dev/null || true
trap - EXIT
