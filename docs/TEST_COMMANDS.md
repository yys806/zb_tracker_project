# OrangePi 云台目标跟踪完整测试命令

本文档记录从项目拷贝到 OrangePi、解压、建立虚拟环境，到 I2C、舵机、摄像头、跟踪闭环的完整测试流程。

## 0. 约定

- OrangePi 用户名示例：`orangepi`
- 项目目录：`/home/orangepi/zb/tracker_project`
- Python 虚拟环境：`/home/orangepi/.venvs/zb`
- PCA9685 I2C 总线：`/dev/i2c-1`
- PCA9685 地址：`0x40`
- 舵机通道：`0 = 俯仰 tilt`，`1 = 水平 pan`
- 所有命令默认在 OrangePi 终端执行，不是在 Windows PowerShell 执行。

## 1. 拷贝和解压项目

查看 U 盘是否识别：

```bash
lsblk
```

查找项目压缩包：

```bash
find /run/media /media /mnt ~/下载 -name "tracker_project_for_orangepi.zip" 2>/dev/null
```

创建工作目录：

```bash
mkdir -p ~/zb
cd ~/zb
```

如已有旧项目，先备份：

```bash
mv tracker_project tracker_project_old
```

解压新项目，把路径替换成 `find` 查到的真实路径：

```bash
unzip /你的U盘路径/tracker_project_for_orangepi.zip
cd ~/zb/tracker_project
```

## 2. 创建和激活 Python 虚拟环境

创建虚拟环境：

```bash
python -m venv ~/.venvs/zb
```

激活虚拟环境：

```bash
source ~/.venvs/zb/bin/activate
```

升级 pip：

```bash
python -m pip install --upgrade pip
```

安装依赖：

```bash
pip install -r requirements.txt
pip install smbus2
```

验证 OpenCV 和 smbus2：

```bash
python -c "import cv2; import smbus2; print('opencv and smbus2 ok')"
```

预期输出：

```text
opencv and smbus2 ok
```

## 3. 验证项目源码包

在项目根目录执行：

```bash
PYTHONPATH=src python -c "import orangepi_tracker; print(orangepi_tracker)"
```

预期输出路径应包含：

```text
/home/orangepi/zb/tracker_project/src/orangepi_tracker/__init__.py
```

运行单元测试：

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

正常结果应为测试全部 `OK`。

## 4. I2C 和 PCA9685 测试

查看系统 I2C 设备：

```bash
ls /dev/i2c-*
```

使用 Python 脚本扫描 I2C。项目里的脚本默认扫描 bus 1：

```bash
sudo PYTHONPATH=src /home/orangepi/.venvs/zb/bin/python tests/scan_i2c.py
```

正常结果应能看到：

```text
Found PCA9685 at 0x40
Found PCA9685 All-Call at 0x70
```

如果没有看到 `0x40`，优先检查：

- PCA9685 `VCC` 是否接 OrangePi 3.3V
- PCA9685 `GND` 是否和 OrangePi 共地
- PCA9685 `SDA` 是否接 40Pin 第 3 脚
- PCA9685 `SCL` 是否接 40Pin 第 5 脚
- OrangePi 是否启用了 `rk3588-i2c1-m4.dtbo` overlay

## 5. 舵机测试

低层 PCA9685 舵机测试：

```bash
sudo /home/orangepi/.venvs/zb/bin/python tests/pca_servo_test.py
```

正常现象：

- 俯仰舵机和水平舵机按角度变化转动
- 没有持续顶住机械结构
- 没有明显卡死或异常发热

主程序舵机测试：

```bash
sudo PYTHONPATH=/home/orangepi/zb/tracker_project/src /home/orangepi/.venvs/zb/bin/python main.py --mode servo-test
```

正常输出类似：

```text
pan=90.0 tilt=90.0
pan=20.0 tilt=90.0
pan=160.0 tilt=90.0
pan=90.0 tilt=35.0
pan=90.0 tilt=145.0
pan=90.0 tilt=90.0
```

同时两个舵机应实际转动。

如果只有输出但舵机不动，执行硬件类诊断：

```bash
sudo PYTHONPATH=/home/orangepi/zb/tracker_project/src /home/orangepi/.venvs/zb/bin/python -c "from orangepi_tracker.config import load_config; from orangepi_tracker.hardware import create_hardware; c=load_config('configs/default_config.json'); h=create_hardware(c.hardware,c.control); print(type(h)); h.move_to(90,90)"
```

正常应输出：

```text
<class 'orangepi_tracker.hardware.SmbusPanTiltHardware'>
```

如果输出 `MockPanTiltHardware`，说明主程序没有连上真实 PCA9685。

## 6. 摄像头测试

查看摄像头设备：

```bash
ls /dev/video*
```

打开摄像头测试窗口：

```bash
sudo PYTHONPATH=/home/orangepi/zb/tracker_project/src /home/orangepi/.venvs/zb/bin/python main.py --mode camera-test
```

正常现象：

- 出现实时摄像头画面
- 按 `q` 退出窗口

如果打不开摄像头，记录 `ls /dev/video*` 和程序报错，再检查 USB 摄像头连接。

## 7. 模拟跟踪测试

模拟模式只测试视觉识别和界面，不控制真实舵机：

```bash
PYTHONPATH=/home/orangepi/zb/tracker_project/src /home/orangepi/.venvs/zb/bin/python main.py --mode track --simulate
```

正常现象：

- 界面显示中心线、目标框、状态、FPS
- 红色高对比目标能被框住
- 目标短暂离开画面后，状态机会进入丢失或搜索状态

## 8. 真实闭环跟踪

确认舵机和摄像头都正常后，再启动真实闭环：

```bash
sudo PYTHONPATH=/home/orangepi/zb/tracker_project/src /home/orangepi/.venvs/zb/bin/python main.py --mode track
```

正常现象：

- 摄像头识别红色高对比目标
- 云台根据目标偏差转动
- 目标尽量保持在画面中心附近
- 运行日志写入 `logs/`

退出方式：

```text
按 q 退出窗口
```

如云台方向反了、抖动明显或打到机械限位，立即 `Ctrl+C` 停止程序，再调整 `configs/default_config.json` 中的通道、角度限位或 PID 参数。

## 9. 日常启动三连

后续演示时可以直接执行：

```bash
source ~/.venvs/zb/bin/activate
cd ~/zb/tracker_project
sudo PYTHONPATH=/home/orangepi/zb/tracker_project/src /home/orangepi/.venvs/zb/bin/python main.py --mode track
```

## 10. 网页监控模式

如果你通过 MobaXterm 远程调试，不方便弹出 OpenCV 窗口，可以启动网页监控模式：

```bash
source ~/.venvs/zb/bin/activate
cd ~/zb/tracker_project
sudo PYTHONPATH=/home/orangepi/zb/tracker_project/src /home/orangepi/.venvs/zb/bin/python main.py --mode web
```

终端会打印类似：

```text
Web monitor running: http://192.168.x.x:5000
```

在电脑浏览器打开这个地址即可看到叠加后的实时画面。退出时回到 MobaXterm，按 `Ctrl+C`。

如果网页打不开，先检查电脑和 OrangePi 是否在同一网络，并确认防火墙没有拦截 `5000` 端口。

也可以手动指定端口：

```bash
sudo PYTHONPATH=/home/orangepi/zb/tracker_project/src /home/orangepi/.venvs/zb/bin/python main.py --mode web --web-port 8080
```

## 11. C/C++ 加速模块测试

构建 C++ 扩展：

```bash
cd ~/zb/tracker_project/cpp_accel
/home/orangepi/.venvs/zb/bin/python setup.py build_ext --inplace
```

回到项目根目录：

```bash
cd ~/zb/tracker_project
```

运行性能对比：

```bash
PYTHONPATH=src:cpp_accel /home/orangepi/.venvs/zb/bin/python scripts/benchmark_morphology.py --config configs/default_config.json --frames 300
```
