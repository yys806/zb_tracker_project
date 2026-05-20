#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

HOST="0.0.0.0"
PORT="9000"
OUTPUT_DIR="$PROJECT_ROOT/cloud_uploads"

while [ $# -gt 0 ]; do
  case "$1" in
    --host)
      HOST="${2:-0.0.0.0}"
      shift 2
      ;;
    --port)
      PORT="${2:-9000}"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR="${2:-$PROJECT_ROOT/cloud_uploads}"
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
echo "[07] start mock cloud"
echo "[07] address: http://$HOST:$PORT"
echo "[07] output: $OUTPUT_DIR"
PYTHONPATH=src "$PYTHON_BIN" scripts/mock_cloud_server.py --host "$HOST" --port "$PORT" --output-dir "$OUTPUT_DIR"
