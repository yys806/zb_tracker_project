#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

BACKEND=""
HOST="0.0.0.0"
PORT="5000"
JPEG="60"
FPS="10"

while [ $# -gt 0 ]; do
  case "$1" in
    --backend)
      BACKEND="${2:-}"
      shift 2
      ;;
    --host)
      HOST="${2:-0.0.0.0}"
      shift 2
      ;;
    --port)
      PORT="${2:-5000}"
      shift 2
      ;;
    --jpeg)
      JPEG="${2:-60}"
      shift 2
      ;;
    --fps)
      FPS="${2:-10}"
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

ARGS=(--mode web --web-host "$HOST" --web-port "$PORT" --web-jpeg-quality "$JPEG" --web-fps "$FPS")
if [ -n "$BACKEND" ]; then
  ARGS+=(--tracker-backend "$BACKEND")
fi

echo "[04.1] remote web real mode"
echo "[04.1] address: $HOST:$PORT"
echo "[04.1] jpeg=$JPEG fps=$FPS"
echo "[04.1] start"
sudo env PYTHONPATH=src "$PYTHON_BIN" main.py "${ARGS[@]}"
