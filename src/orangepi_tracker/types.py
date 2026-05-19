from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple

import numpy as np


BBox = Tuple[int, int, int, int]


@dataclass(slots=True)
class TargetDetection:
    found: bool
    center_x: int = 0
    center_y: int = 0
    bbox: Optional[BBox] = None
    area: float = 0.0
    confidence: float = 0.0
    mask: Optional[np.ndarray] = None


@dataclass(slots=True)
class ControlOutput:
    next_pan: float
    next_tilt: float
    err_x: float
    err_y: float


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

