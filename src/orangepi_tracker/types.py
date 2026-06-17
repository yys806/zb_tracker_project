from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple

import numpy as np


BBox = Tuple[int, int, int, int]
Point = Tuple[int, int]
Connection = Tuple[int, int]


@dataclass(slots=True)
class TargetDetection:
    found: bool
    center_x: int = 0
    center_y: int = 0
    bbox: Optional[BBox] = None
    area: float = 0.0
    confidence: float = 0.0
    mask: Optional[np.ndarray] = None
    mask_ratio: float = 0.0
    message: str = ""


@dataclass(slots=True)
class GestureDetection:
    enabled: bool
    found: bool = False
    label: str = "none"
    finger_count: int = 0
    backend: str = "none"
    center_x: int = 0
    center_y: int = 0
    bbox: Optional[BBox] = None
    area: float = 0.0
    confidence: float = 0.0
    defects: int = 0
    solidity: float = 0.0
    extent: float = 0.0
    landmarks: list[Point] = field(default_factory=list)
    connections: list[Connection] = field(default_factory=list)


@dataclass(slots=True)
class ControlOutput:
    next_pan: float
    next_tilt: float
    err_x: float
    err_y: float


@dataclass(slots=True)
class FlowVector:
    start_x: int
    start_y: int
    end_x: int
    end_y: int
    magnitude: float


@dataclass(slots=True)
class FlowMetrics:
    enabled: bool
    draw_vectors: bool = False
    has_flow: bool = False
    motion_detected: bool = False
    active_points: int = 0
    total_points: int = 0
    mean_magnitude: float = 0.0
    median_magnitude: float = 0.0
    max_magnitude: float = 0.0
    motion_ratio: float = 0.0
    mean_dx: float = 0.0
    mean_dy: float = 0.0
    scale: float = 1.0
    vectors: list[FlowVector] = field(default_factory=list)


@dataclass(slots=True)
class MotionPoint:
    x: int
    y: int


@dataclass(slots=True)
class MotionMetrics:
    enabled: bool
    has_target: bool = False
    speed_px_s: float = 0.0
    smoothed_speed_px_s: float = 0.0
    delta_x_px: float = 0.0
    delta_y_px: float = 0.0
    heading_deg: float = 0.0
    trajectory: list[MotionPoint] = field(default_factory=list)
    heatmap: list[list[float]] = field(default_factory=list)
    heatmap_rows: int = 0
    heatmap_cols: int = 0


@dataclass(slots=True)
class FrameMetrics:
    timestamp: float
    state: str
    detect_time_ms: float
    control_time_ms: float
    fps: float
    err_x: float
    err_y: float
    pan: float
    tilt: float
    target_found: bool
    area: float = 0.0
    confidence: float = 0.0
    mask_ratio: float = 0.0
    bbox: Optional[BBox] = None


@dataclass(slots=True)
class RunSummary:
    frames: int = 0
    found_frames: int = 0
    lost_events: int = 0
    reacquire_times: list[float] = field(default_factory=list)
    total_fps: float = 0.0
    total_abs_err_x: float = 0.0
    total_abs_err_y: float = 0.0
    max_abs_err_x: float = 0.0
    max_abs_err_y: float = 0.0


@dataclass(slots=True)
class QualityMetrics:
    brightness: float = 0.0
    contrast: float = 0.0
    sharpness: float = 0.0
    blur_score: float = 0.0
    exposure_state: str = "unknown"
    occlusion_ratio: float = 0.0
    frame_change: float = 0.0


@dataclass(slots=True)
class TimelineEvent:
    timestamp: float
    kind: str
    message: str
