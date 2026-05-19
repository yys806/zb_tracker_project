from __future__ import annotations

import argparse
import os
import sys
import time

import cv2
import numpy as np


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_ROOT = os.path.join(PROJECT_ROOT, "src")
CPP_ROOT = os.path.join(PROJECT_ROOT, "cpp_accel")
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)
if CPP_ROOT not in sys.path:
    sys.path.insert(0, CPP_ROOT)

from orangepi_tracker.config import load_config
from orangepi_tracker.tracker import cpp_open_close, opencv_open_close, pure_python_open_close


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="比较 OpenCV 与 C++ 形态学模块性能")
    parser.add_argument("--config", default=os.path.join(PROJECT_ROOT, "configs", "default_config.json"))
    parser.add_argument("--frames", type=int, default=60)
    parser.add_argument("--skip-python", action="store_true")
    return parser.parse_args()


def build_masks(frames: int, width: int, height: int) -> list[np.ndarray]:
    rng = np.random.default_rng(42)
    masks: list[np.ndarray] = []
    for _ in range(frames):
        mask = np.zeros((height, width), dtype=np.uint8)
        x = int(rng.integers(50, width - 80))
        y = int(rng.integers(50, height - 80))
        cv2.rectangle(mask, (x, y), (x + 40, y + 40), 255, -1)
        noise_x = rng.integers(0, width, size=150)
        noise_y = rng.integers(0, height, size=150)
        mask[noise_y, noise_x] = 255
        masks.append(mask)
    return masks


def measure(fn, masks: list[np.ndarray], kernel_size: int) -> tuple[float, np.ndarray]:
    start = time.perf_counter()
    last = masks[0]
    for mask in masks:
        last = fn(mask, kernel_size)
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    return elapsed_ms / len(masks), last


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    masks = build_masks(args.frames, config.camera.width, config.camera.height)
    kernel_size = config.tracker.morph_kernel

    python_result = None
    if not args.skip_python:
        python_ms, python_result = measure(pure_python_open_close, masks, kernel_size)
        print(f"Pure Python average time: {python_ms:.3f} ms/frame")

    try:
        cpp_ms, cpp_result = measure(cpp_open_close, masks, kernel_size)
    except Exception as exc:
        print(f"C++ backend unavailable: {exc}")
        return 1

    print(f"C++ average time: {cpp_ms:.3f} ms/frame")
    if python_result is not None:
        same = np.array_equal(python_result, cpp_result)
        print(f"C++ matches Python: {same}")
    else:
        same = True
    if python_result is not None and cpp_ms > 0:
        print(f"Speedup over pure Python: {python_ms / cpp_ms:.2f}x")

    opencv_ms, opencv_result = measure(opencv_open_close, masks, kernel_size)
    print(f"OpenCV average time: {opencv_ms:.3f} ms/frame")
    print(f"C++ matches OpenCV: {np.array_equal(cpp_result, opencv_result)}")
    if python_result is not None:
        print(f"OpenCV matches Python: {np.array_equal(python_result, opencv_result)}")
    if cpp_ms > 0:
        print(f"Speedup over OpenCV: {opencv_ms / cpp_ms:.2f}x")
    return 0 if same else 2


if __name__ == "__main__":
    raise SystemExit(main())
