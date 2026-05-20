#!/usr/bin/env bash
set -euo pipefail

cat <<'EOF'
[15] 常见错误
- ModuleNotFoundError: orangepi_tracker
  -> 命令前加 PYTHONPATH=src
- Permission denied: /dev/i2c-1
  -> 舵机/I2C 命令前加 sudo
- Permission denied: logs/...
  -> 执行 sudo chown -R $(id -u):$(id -g) ~/zb/tracker_project/logs ~/zb/tracker_project/benchmark_results ~/zb/tracker_project/cloud_uploads
- OpenCV xcb / Qt 错误
  -> 用网页监控模式，不依赖桌面窗口
- cpp_whl unavailable
  -> 回到 05 重新构建 wheel
- 舵机顶住结构一直响
  -> 立刻 Ctrl+C，必要时断电
EOF
