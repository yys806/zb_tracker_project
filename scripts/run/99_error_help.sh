#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

exec bash "$RUN_SCRIPT_DIR/15_error_help.sh" "$@"
