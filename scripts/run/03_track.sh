#!/usr/bin/env bash
set -euo pipefail

RUN_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[03] compatibility entry: web console simulate mode"
echo "[03] forwarding to scripts/run/03_web_console_simulate.sh"
exec bash "$RUN_SCRIPT_DIR/03_web_console_simulate.sh" "$@"
