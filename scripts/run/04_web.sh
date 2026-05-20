#!/usr/bin/env bash
set -euo pipefail

RUN_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[04] compatibility entry: web console real mode"
echo "[04] forwarding to scripts/run/04_web_console_real.sh"
exec bash "$RUN_SCRIPT_DIR/04_web_console_real.sh" "$@"
