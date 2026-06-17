# OrangePi Two-Axis Visual Tracking Gimbal

本项目是“综合设计实践 B”课程大作业：基于 OrangePi 5 Pro / RK3588S、USB 摄像头、PCA9685 舵机驱动板和两自由度云台，实现一个可现场演示的实时目标跟踪系统。

系统通过摄像头采集画面，用传统视觉识别高对比便利贴目标，再控制 pan / tilt 两个舵机，让目标中心尽量保持在画面中心。当前主运行方式是网页控制台：浏览器实时看画面，完成中心自动标定，启动跟踪、急停、复位，并查看 FPS、误差、舵机角度、HSV、目标面积和置信度等状态。

## 项目资料

- GitHub 仓库：[yys806/zb_tracker_project](https://github.com/yys806/zb_tracker_project)
- 演示视频：[百度网盘](https://pan.baidu.com/s/1XZiJAh4sCwHBI5ZsC6_X-w?pwd=fva9)
- 完整命令文档：[docs/TEST_COMMANDS.md](docs/TEST_COMMANDS.md)
- 接线表：[docs/wiring_table.xlsx](docs/wiring_table.xlsx)
- 课程报告：[报告/orange_pi_tracker_report/main.pdf](报告/orange_pi_tracker_report/main.pdf)

## 效果预览

| 实际接线 | 网页真实跟踪 |
| --- | --- |
| ![实际接线](docs/assets/wiring_real.jpg) | ![网页真实跟踪](docs/assets/step04_web_real.jpg) |

| FPS 曲线 | 中心误差曲线 | 云台角度曲线 |
| --- | --- | --- |
| ![FPS 曲线](docs/assets/fps_curve.jpg) | ![中心误差曲线](docs/assets/center_error_curve.jpg) | ![云台角度曲线](docs/assets/gimbal_angle_curve.jpg) |

## 硬件配置

| 项目 | 当前配置 |
| --- | --- |
| 主控板 | OrangePi 5 Pro / RK3588S |
| 摄像头 | USB 摄像头，接 OrangePi |
| 舵机驱动 | PCA9685 16 路 PWM 舵机驱动板 |
| I2C 总线 | `/dev/i2c-1` |
| PCA9685 地址 | `0x40`，All-Call 地址 `0x70` |
| 舵机通道 | `channel 0 = tilt`，`channel 1 = pan` |
| Python 环境 | `/home/orangepi/.venvs/zb` |
| OrangePi 项目目录 | `/home/orangepi/zb/tracker_project` |

## 快速运行

在 OrangePi 上进入项目目录：

```bash
cd ~/zb/tracker_project
```

首次导入或重新上传 zip 后，先修复权限并检查环境：

```bash
bash scripts/run/00_import_project.sh
bash scripts/run/01_env_check.sh
```

检查摄像头、I2C 和 PCA9685：

```bash
bash scripts/run/02_hardware_check.sh
```

模拟网页控制台，不动真实舵机：

```bash
bash scripts/run/03_web_console_simulate.sh
```

真实网页控制台，会控制舵机：

```bash
bash scripts/run/04_web_console_real.sh
```

网页默认地址为：

```text
http://<OrangePi-IP>:5000
```

如果网页视频卡顿，可以降低 JPEG 质量和推流帧率：

```bash
bash scripts/run/04_web_console_real.sh --jpeg 45 --fps 20
```

## 推荐演示流程

1. 启动真实网页控制台。
2. 打开 `http://<OrangePi-IP>:5000`。
3. 把便利贴放在画面中心十字线附近。
4. 点击“中心自动标定”。
5. 确认目标框稳定后点击“开始跟踪”。
6. 出现异常时点“急停”。
7. 需要回到初始姿态时点“复位”。

网页启动后默认不会自动跟踪，也不会自动回中。必须先完成中心自动标定，再点击开始跟踪，这样可以避免一启动就误识别背景导致舵机乱动。

## 创新点与加分项

| 创新点 | 实现内容 | 说明 |
| --- | --- | --- |
| 创新点 1 | C++ wheel 视觉算子加速 | 将形态学处理封装为 Python 可调用的 C++/pybind11 wheel，并和 Python / OpenCV / pymp 后端对比 |
| 创新点 2 | 网页远程控制台 | 支持实时画面、中心自动标定、开始跟踪、急停、复位、状态显示、HSV 显示和诊断信息 |
| 创新点 3 | pymp 并行对比 | 提供 pymp 后端与 benchmark，用实验说明小粒度视觉任务中并行调度开销的影响 |
| 创新点 4 | 云端服务接口 | 提供 mock 云端服务和摘要上传脚本，可上传最新跟踪结果与 benchmark 数据 |
| 创新点 5 | 安全云台控制 | 支持限位、限速、死区、最小角度变化抑制、急停、渐进复位和启动释放 PWM |
| 创新点 6 | 扩展诊断模块 | 支持光流统计、轨迹/热力图、画面质量检测、手势识别和大模型诊断接口 |

DNN/RKNN 当前不作为主线实现。原因是本项目验收目标更重视现场稳定闭环，而高对比便利贴跟踪用 HSV + 形状筛选更轻量、可解释、延迟更低。

## 实验结果摘要

代表性真实跟踪日志目录：`logs/20260524_013921`。

| 指标 | 数值 |
| --- | ---: |
| 总帧数 | 2576 |
| 平均 FPS | 23.112 |
| 目标找到率 | 36.80% |
| 平均水平中心误差 | 68.91 px |
| 平均垂直中心误差 | 44.70 px |
| 最大水平中心误差 | 307.00 px |
| 最大垂直中心误差 | 174.00 px |
| 目标丢失次数 | 2 |
| 平均重新捕获时间 | 0.764 s |

说明：这组数据包含调试过程中的目标移出画面、按钮操作和遮挡情况，因此目标找到率偏低。正式展示时建议在干净背景、稳定补光、目标始终在画面内的条件下重新采集一组标准数据。

## C++ wheel 加速结果

| 后端 | 平均耗时 ms/frame | 相对 Python 加速比 | 输出是否匹配 OpenCV |
| --- | ---: | ---: | --- |
| Python | 57.301 | 1.00x | 是 |
| OpenCV | 0.044 | 1291.67x | 是 |
| C++ wheel | 0.353 | 162.54x | 是 |
| pymp | 356.775 | 0.16x | 是 |

![C++ wheel benchmark](docs/assets/step05_cpp_benchmark.jpg)

结论：C++ wheel 相比纯 Python 明显加速，证明“C/C++ 实现 + wheel 封装 + Python 调用”链路完整；OpenCV 仍最快，因为其底层本身就是高度优化的 C/C++ 实现；pymp 在该小粒度任务中较慢，说明并行调度开销大于计算收益。

## 技术路线

1. OpenCV 从 USB 摄像头读取 BGR 图像。
2. 高斯滤波降低噪声。
3. BGR 转 HSV。
4. 根据中心自动标定得到的 HSV 范围生成 mask。
5. 形态学开闭运算去噪和补洞。
6. 根据面积、长宽比、旋转矩形填充率、上一帧位置等条件筛选便利贴候选框。
7. 输出目标中心、bbox、面积、置信度、mask 占比和诊断消息。
8. 控制器根据目标中心与画面中心的偏差输出 pan / tilt 下一角度。
9. PCA9685 输出 PWM 控制两个舵机完成闭环跟踪。

当前版本额外加入了 mask 占比过大拒检、标定中心候选优先、低置信度不驱动舵机、光流默认关闭、目标丢失后保持姿态、搜索时只扫描 pan 不扫 tilt 等稳定性策略。

## 常用命令

```bash
bash scripts/run/01_env_check.sh
bash scripts/run/02_hardware_check.sh
bash scripts/run/03_web_console_simulate.sh
bash scripts/run/04_web_console_real.sh
bash scripts/run/05_cpp_benchmark.sh
bash scripts/run/06_pymp_benchmark.sh
bash scripts/run/07_mock_cloud_upload.sh
bash scripts/run/08_analyze_latest_logs.sh
```

在 Windows 本地跑单元测试：

```powershell
$env:PYTHONPATH = "src"
D:\miniconda\envs\zb\python.exe -m unittest discover -s tests -v
```

在 OrangePi 上跑单元测试：

```bash
cd ~/zb/tracker_project
PYTHONPATH=src /home/orangepi/.venvs/zb/bin/python -m unittest discover -s tests -v
```

## 目录结构

```text
tracker_project/
├── main.py
├── requirements.txt
├── configs/default_config.json
├── cpp_accel/
├── docs/
├── scripts/
├── src/orangepi_tracker/
├── tests/
└── 报告/orange_pi_tracker_report/
```

## 常见问题

| 问题 | 处理方式 |
| --- | --- |
| `ModuleNotFoundError: orangepi_tracker` | 使用项目脚本运行，或在命令前加 `PYTHONPATH=src` |
| OpenCV 窗口远程打不开 | 不用窗口模式，统一运行 `bash scripts/run/04_web_console_real.sh` |
| 网页打不开 | 确认 OrangePi 和电脑网络连通，检查 IP、端口 `5000`，必要时用 USB 转网口共享网络 |
| 摄像头打不开 | 摄像头必须插 OrangePi，先用 `ls /dev/video*` 和 `02_hardware_check.sh` 检查 |
| 舵机不动 | 检查 PCA9685 是否在 `/dev/i2c-1` 的 `0x40`，确认真实模式使用脚本启动 |
| 舵机乱动 | 先点急停；确认已经中心标定后再开始跟踪；检查背景中是否有大面积同色干扰 |
| 检测框闪烁 | 使用纯色便利贴、干净背景和稳定光照；优先选择蓝/绿/黄等与背景差异大的颜色 |
| mask 大面积变白 | 说明背景同色干扰太多，系统会拒检并提示重新标定或更换背景 |
| 复位卡顿 | 复位已采用渐进回中；若仍卡顿，检查机械结构是否顶住，或调整 `tilt_center` |
| C++ benchmark 编译失败 | 运行 `bash scripts/run/05_cpp_benchmark.sh`，脚本会清理旧 build 并重新构建 wheel |
