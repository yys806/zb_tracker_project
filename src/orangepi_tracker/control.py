from __future__ import annotations

from dataclasses import dataclass

from .config import ControlConfig
from .types import ControlOutput


@dataclass
class PIDAxis:
    kp: float
    ki: float
    kd: float
    integral: float = 0.0
    prev_error: float = 0.0

    def update(self, error: float, dt: float) -> float:
        safe_dt = max(dt, 1e-3)
        self.integral += error * safe_dt
        derivative = (error - self.prev_error) / safe_dt
        self.prev_error = error
        return self.kp * error + self.ki * self.integral + self.kd * derivative


class GimbalController:
    def __init__(self, config: ControlConfig) -> None:
        self.config = config
        self.pan_axis = PIDAxis(config.pan_kp, config.pan_ki, config.pan_kd)
        self.tilt_axis = PIDAxis(config.tilt_kp, config.tilt_ki, config.tilt_kd)
        self.current_pan = config.pan_center
        self.current_tilt = config.tilt_center

    def reset(self) -> None:
        self.pan_axis.integral = 0.0
        self.pan_axis.prev_error = 0.0
        self.tilt_axis.integral = 0.0
        self.tilt_axis.prev_error = 0.0
        self.current_pan = self.config.pan_center
        self.current_tilt = self.config.tilt_center

    def _limit_step(self, value: float, center: float) -> float:
        delta = value - center
        delta = max(-self.config.max_step_deg, min(self.config.max_step_deg, delta))
        return center + delta

    def update(self, frame_width: int, frame_height: int, target_center_x: int, target_center_y: int, dt: float) -> ControlOutput:
        err_x = float(target_center_x - frame_width / 2.0)
        err_y = float(target_center_y - frame_height / 2.0)

        if abs(err_x) < self.config.deadzone_px:
            err_x = 0.0
            self.pan_axis.integral = 0.0
            self.pan_axis.prev_error = 0.0
        if abs(err_y) < self.config.deadzone_px:
            err_y = 0.0
            self.tilt_axis.integral = 0.0
            self.tilt_prev_error = 0.0
        raw_pan = self.current_pan - self.pan_axis.update(err_x, dt)
        raw_tilt = self.current_tilt + self.tilt_axis.update(err_y, dt)

        limited_pan = self._limit_step(raw_pan, self.current_pan)
        limited_tilt = self._limit_step(raw_tilt, self.current_tilt)

        next_pan = self.current_pan * self.config.smoothing + limited_pan * (1.0 - self.config.smoothing)
        next_tilt = self.current_tilt * self.config.smoothing + limited_tilt * (1.0 - self.config.smoothing)

        next_pan = max(self.config.pan_min, min(self.config.pan_max, next_pan))
        next_tilt = max(self.config.tilt_min, min(self.config.tilt_max, next_tilt))

        self.current_pan = next_pan
        self.current_tilt = next_tilt
        return ControlOutput(next_pan=next_pan, next_tilt=next_tilt, err_x=err_x, err_y=err_y)

