#!/usr/bin/env bash
set -euo pipefail

RUN_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$RUN_SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_ROOT"
echo "[09] key files"
ls docs/wiring_table.xlsx
ls docs/TEST_COMMANDS.md
ls README.md
echo "[09] outputs"
ls benchmark_results 2>/dev/null || true
ls logs 2>/dev/null || true
ls cloud_uploads 2>/dev/null || true
