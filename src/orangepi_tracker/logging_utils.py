from __future__ import annotations

import csv
import json
import os
from dataclasses import asdict
from datetime import datetime

from .types import FrameMetrics, RunSummary


class TrackingLogger:
    def __init__(self, log_dir: str) -> None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_dir = os.path.join(log_dir, timestamp)
        os.makedirs(self.run_dir, exist_ok=True)
        self.csv_path = os.path.join(self.run_dir, "frames.csv")
        self.summary_path = os.path.join(self.run_dir, "summary.json")
        self.csv_file = open(self.csv_path, "w", newline="", encoding="utf-8")
        self.writer = csv.DictWriter(self.csv_file, fieldnames=list(FrameMetrics.__dataclass_fields__.keys()))
        self.writer.writeheader()

    def log_frame(self, metrics: FrameMetrics) -> None:
        self.writer.writerow(asdict(metrics))

    def write_summary(self, summary: RunSummary) -> None:
        frames = max(summary.frames, 1)
        payload = {
            "frames": summary.frames,
            "found_frames": summary.found_frames,
            "found_ratio": summary.found_frames / frames,
            "avg_fps": summary.total_fps / frames,
            "avg_abs_err_x": summary.total_abs_err_x / frames,
            "avg_abs_err_y": summary.total_abs_err_y / frames,
            "max_abs_err_x": summary.max_abs_err_x,
            "max_abs_err_y": summary.max_abs_err_y,
            "lost_events": summary.lost_events,
            "avg_reacquire_time": (sum(summary.reacquire_times) / len(summary.reacquire_times)) if summary.reacquire_times else None,
            "reacquire_samples": summary.reacquire_times,
        }
        with open(self.summary_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)

    def close(self) -> None:
        self.csv_file.close()

