#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

cd "$PROJECT_ROOT"
echo "[02] list i2c devices"
ls /dev/i2c-* || true
echo "[02] scan PCA9685 on /dev/i2c-1"
sudo env PYTHONPATH=src "$PYTHON_BIN" tests/scan_i2c.py
echo "[02] low level servo test"
sudo "$PYTHON_BIN" tests/pca_servo_test.py
echo "[02] main servo test"
sudo env PYTHONPATH=src "$PYTHON_BIN" main.py --mode servo-test
echo "[02] camera read test"
"$PYTHON_BIN" - <<'PY'
import cv2

cap = cv2.VideoCapture(0)
print("opened =", cap.isOpened())
ok, frame = cap.read()
print("read =", ok)
print("shape =", None if frame is None else frame.shape)
cap.release()
if not ok or frame is None:
    raise SystemExit(1)
PY
