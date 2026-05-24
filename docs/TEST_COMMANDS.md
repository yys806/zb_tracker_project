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

如果卡住了：

```bash
bash scripts/run/99_error_help.sh
```

## 步骤总表

| 步骤 | 命令 | 用途 | 什么时候跑 |
| --- | --- | --- | --- |
| 00 | `bash scripts/run/00_import_project.sh --zip ~/v27.zip` | 把新版本 zip 解压到 `~/zb/tracker_project` | 重传项目时 |
| 01 | `bash scripts/run/01_env_check.sh` | 检查虚拟环境、依赖、单元测试和源码导入 | 每次重传或环境有变时 |
| 02 | `bash scripts/run/02_hardware_check.sh` | 检查 I2C、PCA9685、舵机、摄像头 | 接完线后第一步 |
| 03 | `bash scripts/run/03_web_console_simulate.sh` | 网页控制台模拟模式，不控制真实舵机 | 先验证网页、摄像头、中心自动标定和只读 HSV 显示 |
| 04 | `bash scripts/run/04_web_console_real.sh` | 网页控制台真实模式，控制真实舵机 | 最终主线演示 |
| 05 | `bash scripts/run/05_cpp_benchmark.sh` | 创新点1：C++ whl 视觉算子加速对比 | 主线跑通后 |
| 06 | `bash scripts/run/06_pymp_benchmark.sh` | 创新点3：pymp 并行加速对比 | C++ benchmark 后 |
| 07 | `bash scripts/run/07_mock_cloud_upload.sh` | 创新点4：mock 云端上传最新摘要和 benchmark | 有日志和 benchmark 后 |
| 08 | `bash scripts/run/08_analyze_latest_logs.sh` | 分析最新一次跟踪日志 | 跑完真实跟踪后 |
| 09 | `bash scripts/run/09_check_materials.sh` | 检查最终材料目录 | 交作业前 |
| 99 | `bash scripts/run/99_error_help.sh` | 常见错误速查 | 卡住时 |

补一句最重要的执行原则：

```text
01 -> 02 -> 03 -> 04 是主线。
05 -> 06 -> 07 是加分项验证。
08 -> 04 是收最终数据和最终演示。
DNN/RKNN 暂不进入当前命令流程，等全部做完之后再考虑。
```

## 00. 上传并解压项目

这一步是把电脑上的新版本 zip 放到 OrangePi，然后解压到固定目录。后面所有脚本都默认项目在 `~/zb/tracker_project`。

快捷脚本：

```bash
bash scripts/run/00_import_project.sh --zip ~/v27.zip
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
只允许网页中心自动标定。
网页只读显示当前 HSV，不再手动调 HSV。
标定后程序会动态微调 HSV。
网页只保留中心自动标定、开始跟踪、急停、复位四个按钮。
允许网页开始跟踪、急停、复位，但模拟模式下不会真的动舵机。
```

预期效果：

```text
终端显示网页控制台地址。
电脑浏览器打开 http://OrangePi-IP:5000。
网页能看到实时视频、状态、FPS、pan/tilt、目标状态和当前 HSV。
网页右上角应显示 `v27-status-reset-smooth`。如果没有看到这个版本号，说明浏览器或端口上还是旧页面，需要强制刷新网页或重新运行脚本。
刚打开网页时，状态应显示 SELECT_COLOR 或 READY，舵机不会自动追踪。
默认 `center_on_start=false` 且 `release_on_start=true`，程序启动时不会主动回中，并释放舵机 PWM 避免残留信号乱动。
复位按钮的语义是：先进入急停状态，短暂释放 PWM，再用缓入缓出的更小步长把 pan/tilt 舵机移动到初始角，最后再次释放 PWM。
把目标放画面中心后点击中心自动标定。
确认目标框稳定后，点击开始跟踪，舵机才开始运动。
```

如果视频能动但按钮/状态都没反应，优先按这个顺序处理：

```bash
sudo pkill -f "main.py --mode web" || true
sudo fuser -k 5000/tcp || true
cd ~/zb/tracker_project
bash scripts/run/04_web_console_real.sh
```

然后在浏览器里强制刷新页面，确认右上角能看到 `v27-status-reset-smooth`。当前按钮保留原生表单兜底，即使实时状态不刷新，点击按钮也会向后端发请求。

常用参数：

```bash
bash scripts/run/03_web_console_simulate.sh --jpeg 45 --fps 30
bash scripts/run/03_web_console_simulate.sh --jpeg 40 --fps 20
bash scripts/run/03_web_console_simulate.sh --port 8080
bash scripts/run/03_web_console_simulate.sh --backend cpp
```

默认网页推流目标帧率已经改为 `30 FPS`。如果 Wi-Fi 下网页卡顿，优先降低 JPEG 质量，例如 `--jpeg 40`；如果还是不稳，再把 `--fps` 降到 `20` 或 `15`。

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
网页里只保留中心自动标定，并只读显示当前 HSV。
网页启动后默认不追踪，必须先把目标放中心并自动标定，再点击开始跟踪。
默认不启动自动回中，并释放 PWM；不建议把 `center_on_start` 改成 `true`，否则启动时会主动动舵机。
真实 pan/tilt 舵机会根据目标偏差运动。
网页急停按钮可以暂停舵机动作。
网页只保留中心自动标定、开始跟踪、急停、复位四个按钮；复位按钮会先急停，短暂释放 PWM，再缓入缓出回到初始角，最后再次释放 PWM，减少俯仰舵机咔咔、卡壳和硬顶。
程序退出时不会主动回中，避免关闭网页时舵机突然动作；需要回初始角时请在网页上点“复位”。
```

预期效果：

```text
移动目标时，云台跟随目标转动。
目标尽量回到画面中心。
按网页急停后，舵机不再继续追踪。
急停后如需继续，重新点击开始跟踪。
按复位后，页面状态进入 STOP，云台回到初始角附近。
网页右上角显示 `v27-status-reset-smooth`，表示当前加载的是新版网页控制台。
```

常用参数：

```bash
bash scripts/run/04_web_console_real.sh --jpeg 45 --fps 30
bash scripts/run/04_web_console_real.sh --jpeg 40 --fps 20
bash scripts/run/04_web_console_real.sh --port 8080
bash scripts/run/04_web_console_real.sh --backend cpp
```

舵机动作速度与网页模式下的处理帧率有关。旧版本默认 `10 FPS` 时，舵机最多每秒更新约 10 次，看起来会偏慢；当前版本默认改为 `30 FPS`。

当前识别方法不是 DNN 模型，而是课程里讲的传统 OpenCV 颜色跟踪：先把目标放到画面中心自动标定 HSV，再由程序按 HSV 生成 mask、开闭运算去噪、轮廓筛选。新版会检查旋转最小矩形的正方形程度、矩形填充率和上一帧连续性，短暂 1-5 帧丢检时保持上一帧可靠框，并在跟踪过程中从目标框内部慢速动态微调 HSV，避免光照变化时 mask 一下全黑，也避免 HSV 越调越窄。

如果便利贴识别不稳：

```text
1. 把便利贴放到画面中心十字线附近。
2. 点击中心自动标定。
3. 网页会只读显示当前 HSV 数值。
4. 观察左上角 mask，正常应看到白色目标块而不是全黑。
5. 稳定后直接点击开始跟踪，不再需要保存 HSV。
```

如果舵机仍然左右摇摆：

```text
1. 先把红色识别调稳，因为目标框抖会直接造成舵机抖。
2. 如果目标已经在中心附近还左右小幅摆，编辑 configs/default_config.json。
3. 当前版本 pan 已改成稳健参数：pan_deadzone_px=42、pan_min_delta_deg=0.6、pan_kp=0.035、pan_smoothing=0.35。
4. 如果还抖，先看目标框是否在抖；框稳还抖，再把 pan_deadzone_px 改到 48。
5. 不建议为了左右抖动去加大全局 deadzone_px，因为那会拖慢上下跟踪。
```

如果上下跟踪明显不对：

```text
1. 先看现象：物体在画面上方时，云台应该往上抬，让目标回到中心。
2. 当前版本已经取消了状态机和保持锁对正常纠偏的阻挡：只要框存在，且已经点击开始跟踪，本帧就会根据 err_y 控制 tilt。
3. 当前默认 tilt_direction=1.0，并且俯仰参数参考 v22/v17：tilt_kp=0.16、tilt_max_step_deg=5.0、tilt_smoothing=0.22、tilt_deadzone_px=18、tilt_min_delta_deg=0.25。如果一点开始跟踪后目标在中心却先往下冲，优先确认网页右上角是不是 v27-status-reset-smooth。
4. 如果俯仰舵机上下自激，当前版本以 v22 为基准，关闭 tilt_kd，并使用 tilt_hold_enter_px=24、tilt_hold_release_px=36、tilt_settle_frames=3、tilt_settle_release_px=70。意思是中心附近小抖不动，舵机刚动后的 3 帧忽略小幅画面抖动，明显离开中心才纠偏。如果仍抖，先确认检测框是否稳定，不要先改方向。
5. 如果现场发现上下方向确实反了，编辑 configs/default_config.json，把 tilt_direction 从 1.0 改成 -1.0。
6. 如果方向正确但速度慢，先确认检测框是否稳定；如果框稳定但俯仰仍慢，可把 tilt_kp 小幅加到 0.18，不建议直接加大 tilt_max_step_deg。
7. 如果复位后俯仰没有回到你认为的水平初始角，先确认 configs/default_config.json 里的 tilt_center=90.0 是否就是实际初始角；不是的话按现场机械位置修改 tilt_center。
```

如果便利贴在画面中央但检测框突然闪没：

```text
1. 优先用蓝色或绿色便利贴，背景尽量避开同色物体。
2. 把便利贴放到画面中心，点击中心自动标定，再点击开始跟踪。
3. 新版已经针对 6.5cm 正方形便利贴优化：使用旋转矩形长宽比、填充率、上一帧附近优先、bbox 平滑、lost_hold_frames=5 和动态 HSV。
4. 当前默认关闭动态 HSV，标定时使用 adaptive_hue_margin=18、adaptive_sv_margin=105 生成更宽的固定范围，避免跟踪过程中越调越漂。
5. 如果背景同色干扰很强，把 max_jump_px 从 100 调到 80。
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

## 现在建议的精简顺序

如果 USB 转网口已经稳定、摄像头和舵机也已经接好，日常调试可以直接按这个顺序：

```bash
cd ~/zb/tracker_project
bash scripts/run/01_env_check.sh
bash scripts/run/02_hardware_check.sh
bash scripts/run/03_web_console_simulate.sh
bash scripts/run/04_web_console_real.sh
```

如果你要单独确认 USB 转网口，可以临时运行网络检查脚本，但它不是主线步骤。

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
