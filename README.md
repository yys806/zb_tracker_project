# OrangePi 双自由度云台目标跟踪系统

本项目是“综合设计实践 B”的大作业工程代码。当前主线目标很明确：在 OrangePi 5 Pro / RK3588S 上，用 USB 摄像头采集画面，用 HSV 传统视觉识别高对比目标，再通过 PCA9685 控制两个舵机，让目标尽量保持在画面中心。

当前版本把原来的网页监控升级成了**网页远程控制台**：浏览器里可以看实时画面、查看状态、切换追踪颜色、实时调 HSV、中心自动标定、保存配置、急停、恢复和回中。也就是说，网页控制台已经是主线的一部分，不是单独的支线功能。

## 当前硬件配置

| 项目 | 当前结果 |
| --- | --- |
| 主控板 | OrangePi 5 Pro / RK3588S |
| 摄像头 | USB 摄像头，必须接 OrangePi |
| 舵机驱动 | PCA9685 16 路 PWM 舵机驱动板 |
| I2C 总线 | `/dev/i2c-1` |
| PCA9685 地址 | `0x40`，All-Call 地址 `0x70` |
| 舵机通道 | `channel 0 = tilt`，`channel 1 = pan` |
| Python 环境 | `/home/orangepi/.venvs/zb` |
| OrangePi 项目目录 | `/home/orangepi/zb/tracker_project` |

详细接线表见 [docs/wiring_table.xlsx](docs/wiring_table.xlsx)。

## 已实现功能

| 类型 | 功能 | 状态 |
| --- | --- | --- |
| 主线 | 摄像头采集 | 已实现，OpenCV `VideoCapture(0)` 可读取 USB 摄像头 |
| 主线 | HSV 目标检测 | 已实现，输出中心点、面积、目标框和 mask |
| 主线 | 双舵机闭环控制 | 已实现，根据目标偏差控制 pan/tilt |
| 主线 | 状态机 | 已实现 `IDLE`、`TRACKING`、`LOST_SHORT`、`SEARCH` |
| 主线 | 日志记录 | 已实现，每次运行生成 `frames.csv` 和 `summary.json` |
| 加分项1 | C/C++ whl 视觉算子加速 | 已实现工程代码，可编译 wheel 并对比 Python/OpenCV/C++ |
| 加分项2 | 网页远程控制台 | 已实现颜色切换、HSV 调参、自动标定、实时状态、急停、回中 |
| 加分项3 | pymp 并行加速 | 已实现可选 backend 和 benchmark 对比 |
| 加分项4 | 云端服务/数据上传 | 已实现 mock 云端服务，可上传最新跟踪摘要和 benchmark |
| 加分项5 | 云台安全保护 | 已实现急停、恢复、回中、退出自动回中、限位和限速 |

DNN/RKNN 暂不进入当前命令流程。等主线和上述加分项全部稳定后，如果还有时间，再考虑作为额外扩展。

## 推荐运行顺序

命令不要乱跑。最稳的顺序是：

```bash
cd ~/zb/tracker_project
bash scripts/run/01_env_check.sh
bash scripts/run/02_hardware_check.sh
bash scripts/run/03_web_console_simulate.sh
bash scripts/run/04_web_console_real.sh
```

加分项验证：

```bash
bash scripts/run/05_cpp_benchmark.sh
bash scripts/run/06_pymp_benchmark.sh
bash scripts/run/07_mock_cloud_upload.sh
```

最终收口：

```bash
bash scripts/run/08_analyze_latest_logs.sh
bash scripts/run/04_web_console_real.sh
bash scripts/run/09_check_materials.sh
```

USB 转网口到了以后，检查网络：

```bash
bash scripts/run/10_network_check.sh
```

完整命令说明、每一步作用、预期输出和拆解命令都在 [docs/TEST_COMMANDS.md](docs/TEST_COMMANDS.md)。

## 网页控制台

启动模拟模式：

```bash
bash scripts/run/03_web_console_simulate.sh
```

启动真实模式：

```bash
bash scripts/run/04_web_console_real.sh
```

浏览器打开终端里打印的地址，一般是：

```text
http://OrangePi-IP:5000
```

网页控制台包含：

- 实时视频流和目标框。
- FPS、状态、目标是否找到、pan/tilt、目标面积、置信度。
- 红、蓝、绿、黄、custom 颜色切换。
- HSV 范围实时编辑。
- 中心自动标定。
- 保存配置。
- 急停、恢复跟踪、回中。

## 目录结构

```text
tracker_project/
├── main.py
├── requirements.txt
├── configs/default_config.json
├── cpp_accel/
│   ├── setup.py
│   └── src/morphology_ext.cpp
├── docs/
│   ├── TEST_COMMANDS.md
│   └── wiring_table.xlsx
├── scripts/
│   ├── run/
│   ├── analyze_tracking_logs.py
│   ├── benchmark_morphology.py
│   ├── mock_cloud_server.py
│   └── upload_latest_summary.py
├── src/orangepi_tracker/
└── tests/
```

## 常见问题

| 问题 | 处理方式 |
| --- | --- |
| `ModuleNotFoundError: orangepi_tracker` | 使用脚本运行，或在命令前加 `PYTHONPATH=src` |
| `Permission denied: logs/...` | 脚本会自动尝试修复；手动修复可执行 `sudo chown -R $(id -u):$(id -g) ~/zb/tracker_project/logs ~/zb/tracker_project/benchmark_results ~/zb/tracker_project/cloud_uploads` |
| OpenCV 窗口远程打不开 | 不跑窗口模式，用 `bash scripts/run/04_web_console_real.sh` |
| 舵机不动但程序有输出 | 检查是否真实模式用了 `sudo`，并确认 PCA9685 在 `/dev/i2c-1` 的 `0x40` |
| 舵机方向反了或顶住结构 | 立刻点网页急停，必要时断电，再调配置和限位 |
| 颜色识别不准 | 先切换颜色预设，再用网页 HSV 调参，最后用中心自动标定 |
| C++ benchmark 构建失败 | 先运行 `bash scripts/run/05_cpp_benchmark.sh`，脚本会清理旧 build 权限并重新编译 wheel |
| benchmark 跑得太久 | 默认脚本已经用轻量规模；正式数据可用 `--frames 120 --width 320 --height 240` 加大规模 |
| USB 网口共享网络不确定 | 跑 `bash scripts/run/10_network_check.sh` 检查 IP、路由、DNS 和网页端口 |
