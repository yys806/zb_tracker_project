#!/usr/bin/env bash
set -euo pipefail

cat <<'EOF'
[99] 常见错误
- ModuleNotFoundError: orangepi_tracker
  -> 用脚本运行，或在命令前加 PYTHONPATH=src
- Permission denied: /dev/i2c-1
  -> 舵机/I2C 命令前加 sudo，或运行 02 硬件检查脚本
- Permission denied: logs/...
  -> 执行 sudo chown -R $(id -u):$(id -g) ~/zb/tracker_project/logs ~/zb/tracker_project/benchmark_results ~/zb/tracker_project/cloud_uploads
- OpenCV xcb / Qt 错误
  -> 用网页控制台模式，不跑本地 OpenCV 窗口
- Address already in use
  -> 端口已有旧进程，先执行 pkill -f "main.py --mode web"，或换 --port 8080
- cpp_whl unavailable
  -> 回到 05 重新构建 wheel
- 舵机顶住结构一直响
  -> 立刻点网页急停，必要时断电，再调限位或方向
EOF
