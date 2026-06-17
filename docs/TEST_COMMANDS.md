# OrangePi 云台目标跟踪板端运行与测试命令

本文档记录本项目在 OrangePi 端的部署、运行、硬件检查、主线验证和创新点验证命令。所有命令均在 OrangePi 终端执行，Windows 端仅负责 SSH 连接、浏览器访问和文件传输。

## 运行环境约定

```text
用户名：orangepi
项目目录：/home/orangepi/zb/tracker_project
虚拟环境：/home/orangepi/.venvs/zb
Python：/home/orangepi/.venvs/zb/bin/python
pip：/home/orangepi/.venvs/zb/bin/pip
PCA9685：/dev/i2c-1，地址 0x40
舵机通道：0 = tilt，1 = pan
摄像头：USB 摄像头，接 OrangePi
网页端口：5000
```

## 顺序总览

完整验证流程如下：

```bash
cd ~/zb/tracker_project
bash scripts/run/01_env_check.sh
bash scripts/run/02_hardware_check.sh
bash scripts/run/03_web_console_simulate.sh
bash scripts/run/04_web_console_real.sh
bash scripts/run/05_cpp_benchmark.sh
bash scripts/run/06_pymp_benchmark.sh
bash scripts/run/07_mock_cloud_upload.sh
bash scripts/run/08_analyze_latest_logs.sh
bash scripts/run/09_check_materials.sh
```

各步骤用途如下：

```text
01 环境检查：验证虚拟环境、依赖、源码导入和单元测试。
02 硬件检查：验证摄像头、I2C、PCA9685 和双舵机链路。
03 网页模拟：启动网页控制台，不驱动真实舵机，用于验证视频、检测和按钮接口。
04 网页真实：启动真实跟踪，驱动 pan / tilt 舵机完成主线演示。
05 C++ benchmark：编译并测试 C++ wheel 视觉算子加速模块。
06 pymp benchmark：测试 pymp 并行后端并与其他后端对比。
07 mock 云端：上传最新跟踪摘要和 benchmark 结果到本地 mock 服务。
08 日志分析：分析最新跟踪日志，输出 FPS、误差、丢失次数等统计结果。
09 材料检查：列出最终提交材料、运行日志和实验输出。
```

## 00. 项目导入

当项目以 zip 包形式上传到 OrangePi 后，使用导入脚本解压到固定目录：

```bash
bash scripts/run/00_import_project.sh --zip ~/v27.zip
```

预期输出包括：

```text
[00] 解压: ...
[00] 当前目录: /home/orangepi/zb/tracker_project
```

## 01. 环境检查

```bash
cd ~/zb/tracker_project
bash scripts/run/01_env_check.sh
```

该步骤完成以下验证：

```text
安装 requirements.txt 中的依赖。
验证 cv2、smbus2 能够导入。
验证 orangepi_tracker 源码包能够导入。
运行 tests 目录下的自动化测试。
修复 logs、benchmark_results、cloud_uploads 输出目录权限。
```

预期输出包括：

```text
opencv and smbus2 ok
orangepi_tracker ok
Ran ... tests ... OK
```

## 02. 硬件检查

```bash
cd ~/zb/tracker_project
bash scripts/run/02_hardware_check.sh
```

该步骤完成以下验证：

```text
列出 /dev/i2c-*。
扫描 I2C，确认 PCA9685 在 /dev/i2c-1 上返回 0x40 和 0x70。
运行底层舵机测试。
运行主程序舵机测试。
读取摄像头单帧。
```

预期输出包括：

```text
I2C 扫描结果包含 0x40 和 0x70。
pan / tilt 舵机按测试角度轻微转动。
摄像头读取结果显示 opened=True、read=True、shape=(480, 640, 3) 或同类尺寸。
```

## 03. 网页控制台模拟模式

```bash
cd ~/zb/tracker_project
bash scripts/run/03_web_console_simulate.sh
```

该步骤启动网页控制台，但不驱动真实舵机。系统会读取摄像头，执行 HSV 目标检测，提供 HTTP/MJPEG 网页服务，并显示检测框、目标中心、画面中心线、FPS、HSV、面积、置信度和虚拟 pan / tilt 状态。

浏览器访问：

```text
http://<OrangePi-IP>:5000
```

预期表现：

```text
网页显示实时视频和检测叠加信息。
初始状态不自动跟踪，舵机无动作。
将便利贴目标放在中心后点击“中心自动标定”。
检测框稳定后点击“开始跟踪”。
模拟模式下状态会变化，但真实舵机不运动。
网页右上角显示当前版本标识 v27-status-reset-smooth。
```

常用参数：

```bash
bash scripts/run/03_web_console_simulate.sh --jpeg 45 --fps 30
bash scripts/run/03_web_console_simulate.sh --jpeg 40 --fps 20
bash scripts/run/03_web_console_simulate.sh --port 8080
bash scripts/run/03_web_console_simulate.sh --backend cpp
```

## 04. 网页控制台真实模式

```bash
cd ~/zb/tracker_project
bash scripts/run/04_web_console_real.sh
```

该步骤为系统主线运行入口。系统读取摄像头画面，检测便利贴目标，计算目标中心与画面中心的偏差，并通过 PCA9685 控制 pan / tilt 舵机跟踪目标。

运行流程：

```text
1. 浏览器打开 http://<OrangePi-IP>:5000。
2. 将便利贴目标放在画面中心区域。
3. 点击“中心自动标定”，系统生成当前目标 HSV 范围。
4. 检测框稳定后点击“开始跟踪”。
5. 移动目标，观察云台是否使目标回到画面中心附近。
6. 需要暂停运动时点击“急停”。
7. 需要恢复初始姿态时点击“复位”。
```

预期表现：

```text
目标移动时，云台连续跟随目标转动。
目标中心逐步回到画面中心附近。
急停后舵机停止追踪。
复位后云台平滑回到初始角附近。
网页持续显示 FPS、误差、HSV、目标面积、置信度和 pan / tilt 角度。
```

常用参数：

```bash
bash scripts/run/04_web_console_real.sh --jpeg 45 --fps 30
bash scripts/run/04_web_console_real.sh --jpeg 40 --fps 20
bash scripts/run/04_web_console_real.sh --port 8080
bash scripts/run/04_web_console_real.sh --backend cpp
```

网页推流默认目标帧率为 `30 FPS`。在 Wi-Fi 网络抖动场景中，可通过降低 JPEG 质量和帧率控制网页带宽；在 USB 转网口共享网络场景中，使用 `--jpeg 45 --fps 30` 可保持较高流畅度。

## 目标检测与控制说明

当前主线识别方法为传统 OpenCV 颜色跟踪，不依赖 DNN。算法流程如下：

```text
BGR 图像转换到 HSV。
中心自动标定得到目标 HSV 范围。
按 HSV 范围生成二值 mask。
通过形态学开闭运算去噪和填孔。
筛选轮廓面积、旋转矩形长宽比、矩形填充率和上一帧连续性。
输出目标中心、边界框、面积、置信度和 HSV 状态。
```

当前版本针对 6.5 cm x 6.5 cm 正方形便利贴进行了约束优化。系统使用旋转矩形长宽比、填充率、上一帧附近优先、bbox 平滑和短时丢检保持，降低检测框闪烁和背景同色干扰影响。默认关闭动态 HSV，标定时使用较宽 HSV 范围，避免跟踪过程中 HSV 漂移。

控制部分使用目标中心误差驱动舵机：

```text
水平误差 err_x 控制 pan 舵机。
垂直误差 err_y 控制 tilt 舵机。
控制器加入死区、单帧最大步进、平滑、最小有效角度变化和角度限位。
复位按钮执行急停、短暂释放 PWM、缓入缓出回到初始角、再次释放 PWM。
```

当前关键参数位于 `configs/default_config.json`：

```text
pan_direction=-1.0
tilt_direction=1.0
pan_deadzone_px=30.0
tilt_deadzone_px=24.0
pan_max_step_deg=5.5
tilt_max_step_deg=3.5
pan_smoothing=0.25
tilt_smoothing=0.32
center_on_start=false
release_on_start=true
```

## 04-A. 网页端口占用处理

当 5000 端口已被旧进程占用时，真实模式会出现 `Address already in use`。处理命令如下：

```bash
sudo pkill -f "main.py --mode web" || true
sudo fuser -k 5000/tcp || true
cd ~/zb/tracker_project
bash scripts/run/04_web_console_real.sh
```

浏览器端执行强制刷新后，页面右上角应显示当前版本标识。

## 04-B. 摄像头设备检查

摄像头接入 OrangePi 后执行：

```bash
ls /dev/video*
python - <<'PY'
import cv2
cap = cv2.VideoCapture(0)
print("opened:", cap.isOpened())
ok, frame = cap.read()
print("read:", ok, "shape:", None if frame is None else frame.shape)
cap.release()
PY
```

预期输出：

```text
opened: True
read: True shape: (480, 640, 3)
```

## 04-C. 网络连接说明

远程网页调试依赖电脑与 OrangePi 的网络质量。USB 转网口共享网络比 Wi-Fi 热点更稳定，适合长时间网页视频和 SSH 连接。电脑端浏览器访问：

```text
http://192.168.137.100:5000
```

实际 IP 以 OrangePi 上 `ip addr` 输出为准。

## 05. 创新点 1：C++ wheel 视觉算子加速

```bash
cd ~/zb/tracker_project
bash scripts/run/05_cpp_benchmark.sh
```

该步骤完成以下工作：

```text
清理 cpp_accel 旧 build。
编译 C++/pybind11 扩展为 wheel。
使用 --no-deps 安装本地 wheel。
运行 morphology benchmark。
生成 benchmark_results/morphology_benchmark.json、csv、md。
```

扩大测试规模命令：

```bash
bash scripts/run/05_cpp_benchmark.sh --frames 120 --width 320 --height 240
```

## 06. 创新点 3：pymp 并行加速对比

```bash
cd ~/zb/tracker_project
bash scripts/run/06_pymp_benchmark.sh
```

该步骤用于对比 pymp 后端和其他后端的执行耗时。实验结论用于说明 CPU 密集型小粒度图像算子不能简单依赖 Python thread 或粗粒度并行获得加速。

与 C++ benchmark 使用同样规模时执行：

```bash
bash scripts/run/06_pymp_benchmark.sh --frames 120 --width 320 --height 240
```

## 07. 创新点 4：mock 云端服务与数据上传

```bash
cd ~/zb/tracker_project
bash scripts/run/07_mock_cloud_upload.sh
```

该步骤完成以下工作：

```text
启动本地 mock 云端服务。
读取最新 logs/<timestamp>/summary.json。
读取 benchmark_results/morphology_benchmark.json。
通过 HTTP POST 上传结构化 payload。
在 cloud_uploads 目录保存服务端收到的 JSON 文件。
```

预期输出包括：

```text
dry-run payload
upload success
cloud_uploads/<timestamp>_<run_id>.json
```

## 08. 分析最新日志

```bash
cd ~/zb/tracker_project
bash scripts/run/08_analyze_latest_logs.sh
```

该步骤分析最新一次真实跟踪日志，输出平均 FPS、平均误差、最大误差、目标丢失事件数、搜索事件数和重新捕获时间等指标，并生成报告/PPT 可引用的曲线图。

## 09. 检查最终材料

```bash
cd ~/zb/tracker_project
bash scripts/run/09_check_materials.sh
```

该步骤列出项目最终提交材料、运行日志、benchmark 输出、mock 云端上传结果、报告和文档，用于交付前核对。

## 异常处理脚本

```bash
cd ~/zb/tracker_project
bash scripts/run/99_error_help.sh
```

该脚本输出常见错误与处理命令，覆盖端口占用、权限、摄像头、I2C、Python 导入和网页连接等问题。

## 最终复现实验流程

课程材料复核时，按以下顺序能够复现主线和创新点：

```bash
cd ~/zb/tracker_project
bash scripts/run/01_env_check.sh
bash scripts/run/02_hardware_check.sh
bash scripts/run/03_web_console_simulate.sh
bash scripts/run/04_web_console_real.sh
bash scripts/run/05_cpp_benchmark.sh
bash scripts/run/06_pymp_benchmark.sh
bash scripts/run/07_mock_cloud_upload.sh
bash scripts/run/08_analyze_latest_logs.sh
bash scripts/run/09_check_materials.sh
```

该流程对应报告中的环境验证、硬件验证、网页控制台主线、C++ wheel 加速、pymp 对比、mock 云端上传和日志分析结果。