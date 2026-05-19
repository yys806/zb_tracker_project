# OrangePi 双自由度云台目标跟踪系统

本项目是综合实践大作业工程代码，目标是在 OrangePi 5 Pro / RK3588S 平台上完成一个可现场演示的两自由度云台目标跟踪系统。

系统使用摄像头采集画面，基于 OpenCV/HSV 识别红色高对比目标，通过 PCA9685 控制两个舵机，使目标尽量保持在画面中心。项目还包含运行日志、状态机、搜索重捕逻辑和 C/C++ 视觉算子加速实验。

## 已验证硬件

- OrangePi 5 Pro / RK3588S
- USB 摄像头
- PCA9685 16 路 PWM 舵机驱动板
- 两自由度云台
- 两个舵机
- 独立 5V 舵机供电

当前调试成功的关键配置：

- I2C 总线：`/dev/i2c-1`
- PCA9685 地址：`0x40`
- PCA9685 All-Call 地址：`0x70`
- 舵机通道：`channel 0 = tilt`，`channel 1 = pan`

## 目录结构

```text
tracker_project/
├── main.py
├── requirements.txt
├── configs/
│   └── default_config.json
├── docs/
│   ├── wiring_table.xlsx
│   └── TEST_COMMANDS.md
├── src/
│   └── orangepi_tracker/
│       ├── app.py
│       ├── camera.py
│       ├── config.py
│       ├── control.py
│       ├── hardware.py
│       ├── logging_utils.py
│       ├── overlay.py
│       ├── state_machine.py
│       ├── tracker.py
│       └── types.py
├── tests/
│   ├── scan_i2c.py
│   ├── pca_servo_test.py
│   ├── test_control.py
│   └── test_state_machine.py
├── scripts/
│   └── benchmark_morphology.py
└── cpp_accel/
    ├── setup.py
    └── src/
        └── morphology_ext.cpp
```

## 快速开始

在 OrangePi 上进入项目目录：

```bash
cd ~/zb/tracker_project
```

创建并激活虚拟环境：

```bash
python -m venv ~/.venvs/zb
source ~/.venvs/zb/bin/activate
```

安装依赖：

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install smbus2
```

验证依赖：

```bash
python -c "import cv2; import smbus2; print('opencv and smbus2 ok')"
```

## 运行方式

摄像头测试：

```bash
sudo PYTHONPATH=/home/zbwjy/zb/tracker_project/src /home/zbwjy/.venvs/zb/bin/python main.py --mode camera-test
```

舵机测试：

```bash
sudo PYTHONPATH=/home/zbwjy/zb/tracker_project/src /home/zbwjy/.venvs/zb/bin/python main.py --mode servo-test
```

模拟跟踪，不控制真实舵机：

```bash
PYTHONPATH=/home/zbwjy/zb/tracker_project/src /home/zbwjy/.venvs/zb/bin/python main.py --mode track --simulate
```

真实闭环跟踪：

```bash
sudo PYTHONPATH=/home/zbwjy/zb/tracker_project/src /home/zbwjy/.venvs/zb/bin/python main.py --mode track
```

窗口中按 `q` 退出。

## 核心功能

- 摄像头实时采集
- HSV 红色高对比目标检测
- 目标框、中心点、状态、FPS、云台角度信息叠加
- PCA9685 + 双舵机云台控制
- PID 控制、死区、限位、平滑和最大步进限制
- `IDLE`、`TRACKING`、`LOST_SHORT`、`SEARCH` 状态机
- 目标丢失后小范围搜索重捕
- 运行日志和 summary 输出
- C/C++ 形态学算子加速实验

## 硬件接线

详细接线见：

- `docs/wiring_table.xlsx`

关键连接如下：

| 模块 | 引脚/接口 | 连接到 | 说明 |
| --- | --- | --- | --- |
| PCA9685 | VCC | OrangePi 40Pin 第 1 脚 3.3V | I2C 逻辑电源 |
| PCA9685 | GND | OrangePi 40Pin 第 6 脚 GND | 必须共地 |
| PCA9685 | SDA | OrangePi 40Pin 第 3 脚 SDA | I2C 数据线 |
| PCA9685 | SCL | OrangePi 40Pin 第 5 脚 SCL | I2C 时钟线 |
| PCA9685 | V+ / USB / 绿色端子 | 独立 5V 舵机供电 | 给舵机供电，不建议由 OrangePi USB 供电 |
| 舵机 | channel 0 | PCA9685 0 号通道 | 俯仰 tilt |
| 舵机 | channel 1 | PCA9685 1 号通道 | 水平 pan |

## 完整测试流程

完整命令清单见：

- `docs/TEST_COMMANDS.md`

建议按顺序执行：

1. 拷贝并解压项目
2. 创建虚拟环境并安装依赖
3. 验证项目包和单元测试
4. 扫描 I2C，确认 PCA9685 地址
5. 执行低层舵机测试
6. 执行主程序舵机测试
7. 执行摄像头测试
8. 执行模拟跟踪
9. 执行真实闭环跟踪

## 配置说明

主要配置文件：

```text
configs/default_config.json
```

常用参数：

- `camera.width` / `camera.height`：摄像头分辨率
- `tracker.hsv_ranges`：红色目标 HSV 阈值
- `control.deadzone_px`：中心死区，越大越不容易抖
- `control.pan_min` / `control.pan_max`：水平舵机安全限位
- `control.tilt_min` / `control.tilt_max`：俯仰舵机安全限位
- `hardware.pan_channel`：水平舵机通道，当前为 `1`
- `hardware.tilt_channel`：俯仰舵机通道，当前为 `0`

## C/C++ 加速实验

构建扩展：

```bash
cd ~/zb/tracker_project/cpp_accel
/home/zbwjy/.venvs/zb/bin/python setup.py build_ext --inplace
```

运行对比：

```bash
cd ~/zb/tracker_project
PYTHONPATH=src:cpp_accel /home/zbwjy/.venvs/zb/bin/python scripts/benchmark_morphology.py --config configs/default_config.json --frames 300
```

报告中可对比 Python/OpenCV 版本和 C/C++ 扩展版本的单帧平均耗时、总耗时和加速比。

## 注意事项

- 舵机必须使用独立 5V 供电，PCA9685 和 OrangePi 必须共地。
- 如果舵机持续顶住机械结构、发热或嗡嗡响，应立即断电并调整限位。
- 如果 I2C 扫描看不到 `0x40`，优先检查 SDA/SCL/VCC/GND 和设备树 overlay。
- 如果主程序只打印角度但舵机不动，检查硬件类是否为 `SmbusPanTiltHardware`。
- 正式演示前先运行 `--mode servo-test` 和 `--mode camera-test`，确认硬件状态正常。
