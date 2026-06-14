from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .types import FlowMetrics, FlowVector


@dataclass
class OpticalFlowAnalyzer:
    enabled: bool = True
    use_dense_flow: bool = True
    draw_vectors: bool = False
    motion_threshold: float = 1.2
    motion_ratio_threshold: float = 0.08
    grid_step: int = 24
    max_vectors: int = 80
    min_feature_distance: int = 12
    quality_level: float = 0.01
    block_size: int = 7
    lk_win_size: int = 21
    lk_max_level: int = 2

    def __post_init__(self) -> None:
        self._prev_gray: np.ndarray | None = None
        self._prev_points: np.ndarray | None = None
        self._last_metrics = FlowMetrics(enabled=self.enabled)

    def reset(self) -> None:
        self._prev_gray = None
        self._prev_points = None
        self._last_metrics = FlowMetrics(enabled=self.enabled)

    def process(self, frame: np.ndarray) -> FlowMetrics:
        metrics = FlowMetrics(enabled=self.enabled)
        if not self.enabled:
            self._last_metrics = metrics
            self._prev_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            self._prev_points = None
            return metrics

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if self._prev_gray is None:
            self._prev_gray = gray
            self._prev_points = None
            self._last_metrics = metrics
            return metrics

        if self.use_dense_flow:
            metrics = self._process_dense_flow(gray)
        else:
            metrics = self._process_sparse_flow(gray)

        self._prev_gray = gray
        self._last_metrics = metrics
        return metrics

    def _process_dense_flow(self, gray: np.ndarray) -> FlowMetrics:
        prev_gray = self._prev_gray
        if prev_gray is None:
            return FlowMetrics(enabled=self.enabled)

        flow = cv2.calcOpticalFlowFarneback(
            prev_gray,
            gray,
            None,
            pyr_scale=0.5,
            levels=3,
            winsize=15,
            iterations=3,
            poly_n=5,
            poly_sigma=1.2,
            flags=0,
        )
        h, w = gray.shape[:2]
        step = max(8, int(self.grid_step))
        vectors: list[FlowVector] = []
        magnitudes: list[float] = []
        dx_values: list[float] = []
        dy_values: list[float] = []

        for y in range(step // 2, h, step):
            for x in range(step // 2, w, step):
                dx = float(flow[y, x, 0])
                dy = float(flow[y, x, 1])
                mag = float((dx * dx + dy * dy) ** 0.5)
                magnitudes.append(mag)
                dx_values.append(dx)
                dy_values.append(dy)
                if mag >= self.motion_threshold:
                    end_x = int(round(x + dx * 4.0))
                    end_y = int(round(y + dy * 4.0))
                    vectors.append(FlowVector(x, y, end_x, end_y, mag))

        total_points = len(magnitudes)
        active_points = len(vectors)
        motion_ratio = active_points / total_points if total_points else 0.0
        mean_mag = float(np.mean(magnitudes)) if magnitudes else 0.0
        median_mag = float(np.median(magnitudes)) if magnitudes else 0.0
        max_mag = float(np.max(magnitudes)) if magnitudes else 0.0
        mean_dx = float(np.mean(dx_values)) if dx_values else 0.0
        mean_dy = float(np.mean(dy_values)) if dy_values else 0.0

        return FlowMetrics(
            enabled=True,
            has_flow=total_points > 0,
            motion_detected=motion_ratio >= self.motion_ratio_threshold or mean_mag >= self.motion_threshold,
            active_points=active_points,
            total_points=total_points,
            mean_magnitude=mean_mag,
            median_magnitude=median_mag,
            max_magnitude=max_mag,
            motion_ratio=motion_ratio,
            mean_dx=mean_dx,
            mean_dy=mean_dy,
            scale=4.0,
            vectors=vectors[: self.max_vectors],
        )

    def _process_sparse_flow(self, gray: np.ndarray) -> FlowMetrics:
        prev_gray = self._prev_gray
        if prev_gray is None:
            return FlowMetrics(enabled=self.enabled)

        if self._prev_points is None or len(self._prev_points) < 12:
            points = cv2.goodFeaturesToTrack(
                prev_gray,
                maxCorners=max(40, self.max_vectors),
                qualityLevel=self.quality_level,
                minDistance=self.min_feature_distance,
                blockSize=self.block_size,
            )
            self._prev_points = points

        if self._prev_points is None or len(self._prev_points) == 0:
            return FlowMetrics(enabled=True, has_flow=False)

        next_points, status, err = cv2.calcOpticalFlowPyrLK(
            prev_gray,
            gray,
            self._prev_points,
            None,
            winSize=(self.lk_win_size, self.lk_win_size),
            maxLevel=self.lk_max_level,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 20, 0.03),
        )
        if next_points is None or status is None:
            self._prev_points = None
            return FlowMetrics(enabled=True, has_flow=False)

        good_new = next_points[status.reshape(-1) == 1]
        good_old = self._prev_points[status.reshape(-1) == 1]
        if len(good_new) == 0:
            self._prev_points = None
            return FlowMetrics(enabled=True, has_flow=False)

        vectors: list[FlowVector] = []
        magnitudes: list[float] = []
        dx_values: list[float] = []
        dy_values: list[float] = []
        for old_point, new_point in zip(good_old, good_new):
            ox, oy = float(old_point[0][0]), float(old_point[0][1])
            nx, ny = float(new_point[0][0]), float(new_point[0][1])
            dx = nx - ox
            dy = ny - oy
            mag = float((dx * dx + dy * dy) ** 0.5)
            magnitudes.append(mag)
            dx_values.append(dx)
            dy_values.append(dy)
            if mag >= self.motion_threshold:
                vectors.append(
                    FlowVector(
                        int(round(ox)),
                        int(round(oy)),
                        int(round(nx)),
                        int(round(ny)),
                        mag,
                    )
                )

        total_points = len(good_new)
        active_points = len(vectors)
        motion_ratio = active_points / total_points if total_points else 0.0
        mean_mag = float(np.mean(magnitudes)) if magnitudes else 0.0
        median_mag = float(np.median(magnitudes)) if magnitudes else 0.0
        max_mag = float(np.max(magnitudes)) if magnitudes else 0.0
        mean_dx = float(np.mean(dx_values)) if dx_values else 0.0
        mean_dy = float(np.mean(dy_values)) if dy_values else 0.0

        self._prev_points = good_new.reshape(-1, 1, 2)
        if len(self._prev_points) > self.max_vectors:
            self._prev_points = self._prev_points[: self.max_vectors]

        return FlowMetrics(
            enabled=True,
            has_flow=total_points > 0,
            motion_detected=motion_ratio >= self.motion_ratio_threshold or mean_mag >= self.motion_threshold,
            active_points=active_points,
            total_points=total_points,
            mean_magnitude=mean_mag,
            median_magnitude=median_mag,
            max_magnitude=max_mag,
            motion_ratio=motion_ratio,
            mean_dx=mean_dx,
            mean_dy=mean_dy,
            scale=1.0,
            vectors=vectors[: self.max_vectors],
        )
