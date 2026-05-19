from __future__ import annotations

import argparse
import os
import sys
from typing import TYPE_CHECKING


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_ROOT = os.path.join(PROJECT_ROOT, "src")
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

from orangepi_tracker.config import load_config

if TYPE_CHECKING:
    from orangepi_tracker.config import AppConfig


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OrangePi 两自由度云台目标跟踪系统")
    parser.add_argument("--mode", choices=["track", "camera-test", "servo-test", "web"], default="track")
    parser.add_argument("--config", default=os.path.join("configs", "default_config.json"))
    parser.add_argument("--simulate", action="store_true", help="强制使用模拟硬件")
    parser.add_argument("--web-host", default="0.0.0.0", help="网页监控绑定地址")
    parser.add_argument("--web-port", type=int, default=5000, help="网页监控端口")
    parser.add_argument("--web-jpeg-quality", type=int, default=80, help="网页视频 JPEG 质量")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    from orangepi_tracker.app import TrackingApplication

    config: AppConfig = load_config(args.config)
    if args.simulate:
        config.hardware.force_mock = True

    app = TrackingApplication(config)
    if args.mode == "camera-test":
        return app.run_camera_test()
    if args.mode == "servo-test":
        return app.run_servo_test()
    if args.mode == "web":
        return app.run_web(args.web_host, args.web_port, args.web_jpeg_quality)
    return app.run_tracking()


if __name__ == "__main__":
    raise SystemExit(main())

