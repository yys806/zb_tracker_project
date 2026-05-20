#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

PORT="5000"

while [ $# -gt 0 ]; do
  case "$1" in
    --port)
      PORT="${2:-5000}"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1"
      exit 1
      ;;
  esac
done

echo "[16] network interfaces"
ip -br addr || true

echo
echo "[16] default route"
ip route | sed -n '1,8p' || true

echo
echo "[16] DNS config"
if command -v resolvectl >/dev/null 2>&1; then
  resolvectl status 2>/dev/null | sed -n '1,80p' || true
else
  cat /etc/resolv.conf || true
fi

echo
echo "[16] local web health check"
if command -v curl >/dev/null 2>&1; then
  curl -fsS "http://127.0.0.1:$PORT/health" || echo "[16] local web service is not responding on port $PORT"
else
  "$PYTHON_BIN" - <<PY
from urllib.request import urlopen
try:
    print(urlopen("http://127.0.0.1:$PORT/health", timeout=3).read().decode())
except Exception as exc:
    print(f"[16] local web service is not responding on port $PORT: {exc}")
PY
fi

echo
echo "[16] internet connectivity"
if ping -c 1 -W 2 223.5.5.5 >/dev/null 2>&1; then
  echo "[16] external IP ping ok"
else
  echo "[16] external IP ping failed"
fi

if ping -c 1 -W 2 pypi.org >/dev/null 2>&1; then
  echo "[16] DNS and pypi.org ping ok"
else
  echo "[16] pypi.org ping failed; if only benchmark wheel install is needed, 05 now uses --no-deps"
fi

echo
echo "[16] hint"
echo "If the PC is sharing network over USB Ethernet, OrangePi should have an Ethernet IP and a default route via the PC."
