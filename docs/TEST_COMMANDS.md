# OrangePi 云台目标跟踪完整测试命令

这个文件是项目唯一的命令说明文档。后面调试、演示、做加分项，都按这里从前往后走。

核心思路只有一句：**先跑通网页控制台主线，再跑创新点，最后回到真实跟踪采集最终结果**。网页控制台已经集成到主线里，不再把 OpenCV 本地窗口作为最终演示入口。

当前机器约定：

```text
用户名：orangepi
项目目录：/home/orangepi/zb/tracker_project
虚拟环境：/home/orangepi/.venvs/zb
Python：/home/orangepi/.venvs/zb/bin/python
pip：/home/orangepi/.venvs/zb/bin/pip
PCA9685：/dev/i2c-1，地址 0x40
舵机通道：0 = tilt，1 = pan
摄像头：USB 摄像头，接 OrangePi，不接电脑
```

所有命令默认都在 OrangePi 终端里执行，不是在 Windows PowerShell 里执行。

## 一页总览

完整顺序如下：

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
bash scripts/run/04_web_console_real.sh
bash scripts/run/09_check_materials.sh
```

如果是 USB 网口到了、要检查网络：

```bash
bash scripts/run/10_network_check.sh
```

如果卡住了：

```bash
bash scripts/run/99_error_help.sh
```

## 步骤总表

| 步骤 | 命令 | 用途 | 什么时候跑 |
| --- | --- | --- | --- |
| 00 | `bash scripts/run/00_import_project.sh --zip /你的U盘路径/v5.zip` | 把新版本 zip 解压到 `~/zb/tracker_project` | 重传项目时 |
| 01 | `bash scripts/run/01_env_check.sh` | 检查虚拟环境、依赖、单元测试和源码导入 | 每次重传或环境有变时 |
| 02 | `bash scripts/run/02_hardware_check.sh` | 检查 I2C、PCA9685、舵机、摄像头 | 接完线后第一步 |
| 03 | `bash scripts/run/03_web_console_simulate.sh` | 网页控制台模拟模式，不控制真实舵机 | 先验证网页、摄像头、颜色切换和 HSV 调参 |
| 04 | `bash scripts/run/04_web_console_real.sh` | 网页控制台真实模式，控制真实舵机 | 最终主线演示 |
| 05 | `bash scripts/run/05_cpp_benchmark.sh` | 创新点1：C++ whl 视觉算子加速对比 | 主线跑通后 |
| 06 | `bash scripts/run/06_pymp_benchmark.sh` | 创新点3：pymp 并行加速对比 | C++ benchmark 后 |
| 07 | `bash scripts/run/07_mock_cloud_upload.sh` | 创新点4：mock 云端上传最新摘要和 benchmark | 有日志和 benchmark 后 |
| 08 | `bash scripts/run/08_analyze_latest_logs.sh` | 分析最新一次跟踪日志 | 跑完真实跟踪后 |
| 09 | `bash scripts/run/09_check_materials.sh` | 检查最终材料目录 | 交作业前 |
| 10 | `bash scripts/run/10_network_check.sh` | 检查 USB 网口共享网络、路由、DNS、网页端口 | USB 转网口到了以后 |
| 99 | `bash scripts/run/99_error_help.sh` | 常见错误速查 | 卡住时 |

补一句最重要的执行原则：

```text
01 -> 02 -> 03 -> 04 是主线。
05 -> 06 -> 07 是加分项验证。
08 -> 04 是收最终数据和最终演示。
10 是网络检查，不是每天都必须跑。
DNN/RKNN 暂不进入当前命令流程，等全部做完之后再考虑。
```

## 00. 上传并解压项目

这一步是把电脑上的新版本 zip 放到 OrangePi，然后解压到固定目录。后面所有脚本都默认项目在 `~/zb/tracker_project`。

快捷脚本：

```bash
bash scripts/run/00_import_project.sh --zip /你的U盘路径/v5.zip
```

预期效果：

```text
终端显示 [00] 解压: ...
最后显示 [00] 当前目录: /home/orangepi/zb/tracker_project
```

## 01. 检查环境和依赖

快捷脚本：

```bash
cd ~/zb/tracker_project
bash scripts/run/01_env_check.sh
```

这一步做什么：

```text
安装 requirements.txt 里的依赖。
验证 cv2、smbus2 能导入。
验证 orangepi_tracker 源码包能导入。
运行 tests 目录下的单元测试。
修复 logs、benchmark_results、cloud_uploads 输出目录权限。
```

预期效果：

```text
看到 opencv and smbus2 ok
看到 unittest 显示 OK
```

## 02. 检查硬件链路

快捷脚本：

```bash
cd ~/zb/tracker_project
bash scripts/run/02_hardware_check.sh
```

这一步做什么：

```text
列出 /dev/i2c-*。
扫描 I2C，确认 PCA9685 在 /dev/i2c-1 上能看到 0x40 和 0x70。
运行底层舵机测试。
运行主程序舵机测试。
读取摄像头单帧。
```

预期效果：

```text
I2C 扫描看到 0x40 和 0x70。
舵机会按测试角度轻微转动。
摄像头读取显示 opened = True、read = True、shape = (480, 640, 3) 或类似尺寸。
```

## 03. 网页控制台模拟模式

这是新的主线第一步。它会启动网页控制台，但不控制真实舵机。

快捷脚本：

```bash
cd ~/zb/tracker_project
bash scripts/run/03_web_console_simulate.sh
```

这一步做什么：

```text
启动摄像头读取。
启动 HSV 目标检测。
启动 HTTP/MJPEG 网页控制台。
允许网页切换红/蓝/绿/黄/custom。
允许网页实时调 HSV。
允许网页中心自动标定。
允许网页保存配置。
允许网页急停、恢复、回中，但模拟模式下不会真的动舵机。
```

预期效果：

```text
终端显示网页控制台地址。
电脑浏览器打开 http://OrangePi-IP:5000。
网页能看到实时视频、状态、FPS、pan/tilt、当前颜色和 HSV。
切换颜色或调 HSV 后，目标框会跟着变化。
```

常用参数：

```bash
bash scripts/run/03_web_console_simulate.sh --jpeg 45 --fps 8
bash scripts/run/03_web_console_simulate.sh --port 8080
bash scripts/run/03_web_console_simulate.sh --backend cpp
```

## 04. 网页控制台真实模式

这是最终主线演示命令。它会控制真实舵机。

快捷脚本：

```bash
cd ~/zb/tracker_project
bash scripts/run/04_web_console_real.sh
```

这一步做什么：

```text
摄像头识别目标。
网页控制台显示实时画面和状态。
网页里可以切换目标颜色、调 HSV、自动标定。
真实 pan/tilt 舵机会根据目标偏差运动。
网页急停按钮可以暂停舵机动作。
网页回中按钮可以让云台回到中心角。
程序退出时会尝试自动回中。
```

预期效果：

```text
移动目标时，云台跟随目标转动。
目标尽量回到画面中心。
按网页急停后，舵机不再继续追踪。
按恢复跟踪后，舵机继续工作。
按回中后，云台回到中心附近。
```

常用参数：

```bash
bash scripts/run/04_web_console_real.sh --jpeg 45 --fps 8
bash scripts/run/04_web_console_real.sh --port 8080
bash scripts/run/04_web_console_real.sh --backend cpp
```

## 05. 创新点1：C++ whl 视觉算子加速

快捷脚本：

```bash
cd ~/zb/tracker_project
bash scripts/run/05_cpp_benchmark.sh
```

这一步做什么：

```text
清理 cpp_accel 旧 build。
编译 C++/pybind11 扩展为 whl。
用 --no-deps 安装本地 whl，避免 OrangePi 没网时去 PyPI 找依赖。
运行 benchmark，对比 Python、OpenCV、C++ whl、pymp。
生成 benchmark_results/morphology_benchmark.json、csv、md。
```

默认 benchmark 用 `10` 帧、`80x60` 小图，目的是让 OrangePi 很快跑完，先拿到可展示结果。要做更正式的数据，可以加大规模：

```bash
bash scripts/run/05_cpp_benchmark.sh --frames 120 --width 320 --height 240
```

## 06. 创新点3：pymp 并行加速对比

快捷脚本：

```bash
cd ~/zb/tracker_project
bash scripts/run/06_pymp_benchmark.sh
```

这一步做什么：

```text
重点测试 pymp backend。
用于说明 Python thread 不适合 CPU 密集加速，因此尝试 pymp。
```

默认也是轻量规模。如果要和 C++ benchmark 使用同样规模：

```bash
bash scripts/run/06_pymp_benchmark.sh --frames 120 --width 320 --height 240
```

## 07. 创新点4：云端服务/数据上传

快捷脚本：

```bash
cd ~/zb/tracker_project
bash scripts/run/07_mock_cloud_upload.sh
```

这一步做什么：

```text
启动本机 mock 云端服务。
读取最新一次 logs/<timestamp>/summary.json。
读取 benchmark_results/morphology_benchmark.json。
通过 HTTP POST 上传到 mock 服务。
```

预期效果：

```text
终端先打印 dry-run payload。
随后显示上传成功。
cloud_uploads 目录下出现收到的 JSON 文件。
```

## 08. 分析最新日志

快捷脚本：

```bash
cd ~/zb/tracker_project
bash scripts/run/08_analyze_latest_logs.sh
```

这一步做什么：

```text
分析最新一次真实跟踪日志。
输出平均 FPS、平均误差、最大误差、目标丢失事件数、搜索事件数等。
生成后续报告/PPT 可用的数据和图。
```

## 09. 检查最终材料

快捷脚本：

```bash
cd ~/zb/tracker_project
bash scripts/run/09_check_materials.sh
```

这一步做什么：

```text
列出 logs、benchmark_results、cloud_uploads、docs 等关键材料。
用于交作业前检查有没有缺东西。
```

## 10. USB 网口/共享网络检查

快捷脚本：

```bash
cd ~/zb/tracker_project
bash scripts/run/10_network_check.sh
```

这一步做什么：

```text
列出网络接口和 IP。
检查默认路由。
检查 DNS。
检查网页控制台健康接口。
如果电脑通过 USB 转网口共享网络，OrangePi 应该能拿到有线 IP。
```

## 99. 常见错误速查

快捷脚本：

```bash
cd ~/zb/tracker_project
bash scripts/run/99_error_help.sh
```

## 最终演示建议

第一次完整验证：

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

最后收口：

```bash
bash scripts/run/08_analyze_latest_logs.sh
bash scripts/run/04_web_console_real.sh
bash scripts/run/09_check_materials.sh
```
