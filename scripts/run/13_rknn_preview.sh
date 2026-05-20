#!/usr/bin/env bash
set -euo pipefail

cat <<'EOF'
[13] DNN/RKNN 扩展预案
当前主线优先保证传统视觉闭环稳定。
如果后续要做 DNN/RKNN，建议按：
1. 轻量模型导出 ONNX
2. PC 上验证
3. RKNN-Toolkit2 转换
4. RK3588S 上部署
5. 接入现有 TargetDetection 和状态机
EOF
