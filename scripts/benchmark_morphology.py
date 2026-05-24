from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Callable

import cv2
import numpy as np


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_ROOT = os.path.join(PROJECT_ROOT, "src")
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

from orangepi_tracker.config import load_config
from orangepi_tracker.tracker import (
    cpp_open_close,
    opencv_open_close,
    pure_python_open_close,
    pymp_open_close,
)


MorphFn = Callable[[np.ndarray, int], np.ndarray]


@dataclass(slots=True)
class BackendResult:
    backend: str
    available: bool
    avg_ms: float | None
    total_ms: float | None
    speedup_vs_python: float | None
    matches_opencv: bool | None
    error: str | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark morphology backends for the OrangePi tracking project")
    parser.add_argument("--config", default=os.path.join(PROJECT_ROOT, "configs", "default_config.json"))
    parser.add_argument("--frames", type=int, default=10)
    parser.add_argument("--width", type=int, default=None)
    parser.add_argument("--height", type=int, default=None)
    parser.add_argument("--output-dir", default=os.path.join(PROJECT_ROOT, "benchmark_results"))
    parser.add_argument("--skip-python", action="store_true", help="Skip slow pure Python backend")
    parser.add_argument("--include-pymp", action="store_true", help="Also benchmark pymp backend if installed")
    parser.add_argument(
        "--local-cpp-dir",
        default=None,
        help="Optional directory containing morphology_ext*.so; normally use installed wheel instead",
    )
    return parser.parse_args()


def build_masks(frames: int, width: int, height: int) -> list[np.ndarray]:
    rng = np.random.default_rng(42)
    masks: list[np.ndarray] = []
    for _ in range(frames):
        mask = np.zeros((height, width), dtype=np.uint8)
        x = int(rng.integers(20, max(21, width - 80)))
        y = int(rng.integers(20, max(21, height - 80)))
        w = int(rng.integers(24, 72))
        h = int(rng.integers(24, 72))
        cv2.rectangle(mask, (x, y), (min(width - 1, x + w), min(height - 1, y + h)), 255, -1)
        noise_x = rng.integers(0, width, size=max(40, width * height // 2000))
        noise_y = rng.integers(0, height, size=max(40, width * height // 2000))
        mask[noise_y, noise_x] = 255
        masks.append(mask)
    return masks


def measure(fn: MorphFn, masks: list[np.ndarray], kernel_size: int) -> tuple[float, float, np.ndarray, list[float]]:
    start = time.perf_counter()
    last = masks[0]
    frame_times: list[float] = []
    for mask in masks:
        frame_start = time.perf_counter()
        last = fn(mask, kernel_size)
        frame_times.append((time.perf_counter() - frame_start) * 1000.0)
    total_ms = (time.perf_counter() - start) * 1000.0
    return total_ms / len(masks), total_ms, last, frame_times


def run_backend(
    name: str,
    fn: MorphFn,
    masks: list[np.ndarray],
    kernel_size: int,
    reference: np.ndarray,
    python_avg_ms: float | None,
):
    try:
        avg_ms, total_ms, result, frame_times = measure(fn, masks, kernel_size)
    except Exception as exc:
        return BackendResult(
            backend=name,
            available=False,
            avg_ms=None,
            total_ms=None,
            speedup_vs_python=None,
            matches_opencv=None,
            error=str(exc),
        ), []

    speedup = (python_avg_ms / avg_ms) if python_avg_ms is not None and avg_ms > 0 else None
    return BackendResult(
        backend=name,
        available=True,
        avg_ms=avg_ms,
        total_ms=total_ms,
        speedup_vs_python=speedup,
        matches_opencv=bool(np.array_equal(result, reference)),
    ), frame_times


def save_results(output_dir: str, payload: dict, rows: list[BackendResult], frame_table: dict[str, list[float]]) -> None:
    os.makedirs(output_dir, exist_ok=True)
    json_path = os.path.join(output_dir, "morphology_benchmark.json")
    csv_path = os.path.join(output_dir, "morphology_benchmark.csv")
    md_path = os.path.join(output_dir, "morphology_benchmark.md")
    detail_csv_path = os.path.join(output_dir, "morphology_benchmark_frames.csv")

    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["backend", "available", "avg_ms", "total_ms", "speedup_vs_python", "matches_opencv", "error"],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))

    with open(detail_csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        backends = [row.backend for row in rows if row.available]
        writer.writerow(["frame_index", *backends])
        frame_count = max((len(times) for times in frame_table.values()), default=0)
        for frame_index in range(frame_count):
            row = [frame_index]
            for backend in backends:
                times = frame_table.get(backend, [])
                row.append("" if frame_index >= len(times) else f"{times[frame_index]:.6f}")
            writer.writerow(row)

    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write("# Morphology Benchmark\n\n")
        fh.write(f"- Generated at: `{payload['generated_at']}`\n")
        fh.write(f"- Frames: `{payload['frames']}`\n")
        fh.write(f"- Resolution: `{payload['width']}x{payload['height']}`\n")
        fh.write(f"- Kernel size: `{payload['kernel_size']}`\n\n")
        fh.write("| Backend | Available | Avg ms/frame | Speedup vs Python | Matches OpenCV |\n")
        fh.write("|---|---:|---:|---:|---:|\n")
        for row in rows:
            avg = "" if row.avg_ms is None else f"{row.avg_ms:.3f}"
            speedup = "" if row.speedup_vs_python is None else f"{row.speedup_vs_python:.2f}x"
            matches = "" if row.matches_opencv is None else str(row.matches_opencv)
            fh.write(f"| {row.backend} | {row.available} | {avg} | {speedup} | {matches} |\n")

    print(f"Saved benchmark JSON: {json_path}")
    print(f"Saved benchmark CSV:  {csv_path}")
    print(f"Saved benchmark frame CSV: {detail_csv_path}")
    print(f"Saved benchmark MD:   {md_path}")


def main() -> int:
    args = parse_args()
    if args.local_cpp_dir and args.local_cpp_dir not in sys.path:
        sys.path.insert(0, args.local_cpp_dir)

    config = load_config(args.config)
    width = args.width or config.camera.width
    height = args.height or config.camera.height
    frames = max(1, args.frames)
    kernel_size = config.tracker.morph_kernel

    masks = build_masks(frames, width, height)
    opencv_avg_ms, opencv_total_ms, opencv_reference, opencv_frames = measure(opencv_open_close, masks, kernel_size)
    frame_table: dict[str, list[float]] = {"opencv": opencv_frames}

    rows: list[BackendResult] = [
        BackendResult(
            backend="opencv",
            available=True,
            avg_ms=opencv_avg_ms,
            total_ms=opencv_total_ms,
            speedup_vs_python=None,
            matches_opencv=True,
        )
    ]

    python_avg_ms: float | None = None
    if not args.skip_python:
        python_row, python_frames = run_backend("python", pure_python_open_close, masks, kernel_size, opencv_reference, None)
        rows.append(python_row)
        frame_table["python"] = python_frames
        if python_row.available:
            python_avg_ms = python_row.avg_ms

    cpp_row, cpp_frames = run_backend("cpp_whl", cpp_open_close, masks, kernel_size, opencv_reference, python_avg_ms)
    rows.append(cpp_row)
    frame_table["cpp_whl"] = cpp_frames

    if args.include_pymp:
        pymp_row, pymp_frames = run_backend("pymp", pymp_open_close, masks, kernel_size, opencv_reference, python_avg_ms)
        rows.append(pymp_row)
        frame_table["pymp"] = pymp_frames

    if python_avg_ms is not None:
        for row in rows:
            if row.available and row.avg_ms and row.speedup_vs_python is None:
                row.speedup_vs_python = python_avg_ms / row.avg_ms

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "frames": frames,
        "width": width,
        "height": height,
        "kernel_size": kernel_size,
        "results": [asdict(row) for row in rows],
        "frame_times": frame_table,
    }
    save_results(args.output_dir, payload, rows, frame_table)

    print("\nBenchmark results")
    for row in rows:
        if not row.available:
            print(f"- {row.backend}: unavailable ({row.error})")
            continue
        speedup = "" if row.speedup_vs_python is None else f", speedup vs Python {row.speedup_vs_python:.2f}x"
        print(f"- {row.backend}: {row.avg_ms:.3f} ms/frame{speedup}, matches OpenCV={row.matches_opencv}")

    failed_match = [row.backend for row in rows if row.available and row.matches_opencv is False]
    return 2 if failed_match else 0


if __name__ == "__main__":
    raise SystemExit(main())
