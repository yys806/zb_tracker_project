from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import math

from .types import MotionMetrics, MotionPoint


@dataclass
class MotionAnalyzer:
    enabled: bool = True
    trajectory_limit: int = 180
    heatmap_rows: int = 8
    heatmap_cols: int = 12
    speed_smoothing: float = 0.25

    def __post_init__(self) -> None:
        self._trajectory: deque[MotionPoint] = deque(maxlen=max(16, self.trajectory_limit))
        self._heatmap = [[0.0 for _ in range(max(1, self.heatmap_cols))] for _ in range(max(1, self.heatmap_rows))]
        self._last_center: tuple[float, float] | None = None
        self._last_timestamp: float | None = None
        self._smoothed_speed = 0.0
        self._last_frame_size: tuple[int, int] | None = None

    def reset(self) -> None:
        self._trajectory.clear()
        self._heatmap = [[0.0 for _ in range(max(1, self.heatmap_cols))] for _ in range(max(1, self.heatmap_rows))]
        self._last_center = None
        self._last_timestamp = None
        self._smoothed_speed = 0.0
        self._last_frame_size = None

    def update(
        self,
        frame_width: int,
        frame_height: int,
        center_x: int | None,
        center_y: int | None,
        timestamp: float,
        target_found: bool,
    ) -> MotionMetrics:
        self._last_frame_size = (frame_width, frame_height)
        if not self.enabled:
            return MotionMetrics(enabled=False)

        if not target_found or center_x is None or center_y is None:
            self._last_center = None
            self._last_timestamp = timestamp
            self._smoothed_speed = 0.0
            return self._snapshot(False, 0.0, 0.0, 0.0, 0.0)

        current = (float(center_x), float(center_y))
        if self._last_center is None or self._last_timestamp is None:
            self._last_center = current
            self._last_timestamp = timestamp
            self._append_point(center_x, center_y)
            self._accumulate_heatmap(center_x, center_y, 1.0)
            return self._snapshot(True, 0.0, 0.0, 0.0, 0.0)

        dt = max(timestamp - self._last_timestamp, 1e-3)
        dx = current[0] - self._last_center[0]
        dy = current[1] - self._last_center[1]
        speed = math.hypot(dx, dy) / dt
        alpha = max(0.0, min(1.0, float(self.speed_smoothing)))
        self._smoothed_speed = self._smoothed_speed * alpha + speed * (1.0 - alpha)
        self._last_center = current
        self._last_timestamp = timestamp
        self._append_point(center_x, center_y)
        self._accumulate_heatmap(center_x, center_y, 1.0)
        heading = math.degrees(math.atan2(-dy, dx)) if dx != 0.0 or dy != 0.0 else 0.0
        return self._snapshot(True, speed, self._smoothed_speed, dx, dy, heading)

    def _append_point(self, x: int, y: int) -> None:
        self._trajectory.append(MotionPoint(x=x, y=y))

    def _accumulate_heatmap(self, x: int, y: int, weight: float) -> None:
        width = self._last_frame_size[0] if self._last_frame_size else 1
        height = self._last_frame_size[1] if self._last_frame_size else 1
        col = min(max(int(x / max(width, 1) * self.heatmap_cols), 0), self.heatmap_cols - 1)
        row = min(max(int(y / max(height, 1) * self.heatmap_rows), 0), self.heatmap_rows - 1)
        self._heatmap[row][col] += weight

    def _snapshot(
        self,
        has_target: bool,
        speed: float,
        smoothed_speed: float,
        dx: float,
        dy: float,
        heading: float = 0.0,
    ) -> MotionMetrics:
        return MotionMetrics(
            enabled=True,
            has_target=has_target,
            speed_px_s=speed,
            smoothed_speed_px_s=smoothed_speed,
            delta_x_px=dx,
            delta_y_px=dy,
            heading_deg=heading,
            trajectory=list(self._trajectory),
            heatmap=[row[:] for row in self._heatmap],
            heatmap_rows=self.heatmap_rows,
            heatmap_cols=self.heatmap_cols,
        )


@dataclass
class FrameQualityAnalyzer:
    enabled: bool = True
    history_limit: int = 120

    def __post_init__(self) -> None:
        self._prev_gray = None
        self._last_brightness = 0.0
        self._last_contrast = 0.0
        self._last_sharpness = 0.0
        self._last_blur_score = 0.0
        self._last_exposure_state = "unknown"
        self._last_occlusion_ratio = 0.0
        self._last_frame_change = 0.0

    def reset(self) -> None:
        self._prev_gray = None
        self._last_brightness = 0.0
        self._last_contrast = 0.0
        self._last_sharpness = 0.0
        self._last_blur_score = 0.0
        self._last_exposure_state = "unknown"
        self._last_occlusion_ratio = 0.0
        self._last_frame_change = 0.0

    def update(self, frame) -> dict:
        if not self.enabled:
            return {
                "brightness": 0.0,
                "contrast": 0.0,
                "sharpness": 0.0,
                "blur_score": 0.0,
                "exposure_state": "disabled",
                "occlusion_ratio": 0.0,
                "frame_change": 0.0,
            }

        import cv2
        import numpy as np

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        brightness = float(np.mean(gray))
        contrast = float(np.std(gray))
        lap = cv2.Laplacian(gray, cv2.CV_64F)
        sharpness = float(lap.var())
        blur_score = 1.0 / max(sharpness, 1e-6)
        if brightness < 42:
            exposure_state = "dark"
        elif brightness > 210:
            exposure_state = "bright"
        else:
            exposure_state = "normal"
        occlusion_ratio = float(np.mean(gray < 18))
        frame_change = 0.0
        if self._prev_gray is not None:
            diff = cv2.absdiff(gray, self._prev_gray)
            frame_change = float(np.mean(diff) / 255.0)
        self._prev_gray = gray
        self._last_brightness = brightness
        self._last_contrast = contrast
        self._last_sharpness = sharpness
        self._last_blur_score = blur_score
        self._last_exposure_state = exposure_state
        self._last_occlusion_ratio = occlusion_ratio
        self._last_frame_change = frame_change
        return {
            "brightness": round(brightness, 2),
            "contrast": round(contrast, 2),
            "sharpness": round(sharpness, 2),
            "blur_score": round(blur_score, 4),
            "exposure_state": exposure_state,
            "occlusion_ratio": round(occlusion_ratio, 3),
            "frame_change": round(frame_change, 3),
        }
