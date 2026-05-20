#!/usr/bin/env bash
set -euo pipefail

RUN_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

exec bash "$RUN_SCRIPT_DIR/14_check_materials.sh" "$@"
