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
        self.tilt_hold_locked = False
        self.tilt_settle_remaining = 0

    def reset(self) -> None:
        self.pan_axis.integral = 0.0
        self.pan_axis.prev_error = 0.0
        self.tilt_axis.integral = 0.0
        self.tilt_axis.prev_error = 0.0
        self.current_pan = self.config.pan_center
        self.current_tilt = self.config.tilt_center
        self.tilt_hold_locked = False
        self.tilt_settle_remaining = 0

    @staticmethod
    def _limit_step(value: float, center: float, max_step: float) -> float:
        delta = value - center
        delta = max(-max_step, min(max_step, delta))
        return center + delta

    @staticmethod
    def _apply_deadzone(error: float, deadzone: float) -> float:
        if abs(error) <= deadzone:
            return 0.0
        if error > 0.0:
            return error - deadzone
        return error + deadzone

    def _apply_tilt_hold_hysteresis(self, err_y: float, tilt_deadzone: float) -> float:
        enter = self.config.tilt_hold_enter_px
        release = self.config.tilt_hold_release_px
        if enter is None and release is None:
            return err_y
        enter_px = max(float(tilt_deadzone), float(enter if enter is not None else tilt_deadzone))
        release_px = max(enter_px, float(release if release is not None else enter_px))
        abs_error = abs(err_y)
        if self.tilt_hold_locked:
            if abs_error <= release_px:
                return 0.0
            self.tilt_hold_locked = False
            return err_y
        if abs_error <= enter_px:
            self.tilt_hold_locked = True
            return 0.0
        return err_y

    def _apply_tilt_settle_filter(self, err_y: float, frame_height: int) -> float:
        if self.tilt_settle_remaining <= 0:
            return err_y
        release = self.config.tilt_settle_release_px
        release_px = float(release if release is not None else frame_height * 0.18)
        if abs(err_y) < max(0.0, release_px):
            self.tilt_settle_remaining -= 1
            return 0.0
        self.tilt_settle_remaining = 0
        return err_y

    def update(self, frame_width: int, frame_height: int, target_center_x: int, target_center_y: int, dt: float) -> ControlOutput:
        err_x = float(target_center_x - frame_width / 2.0)
        err_y = float(target_center_y - frame_height / 2.0)
        pan_deadzone = self.config.pan_deadzone_px if self.config.pan_deadzone_px is not None else self.config.deadzone_px
        tilt_deadzone = self.config.tilt_deadzone_px if self.config.tilt_deadzone_px is not None else self.config.deadzone_px
        pan_min_delta = self.config.pan_min_delta_deg if self.config.pan_min_delta_deg is not None else self.config.servo_min_delta_deg
        tilt_min_delta = self.config.tilt_min_delta_deg if self.config.tilt_min_delta_deg is not None else self.config.servo_min_delta_deg
        pan_max_step = self.config.pan_max_step_deg if self.config.pan_max_step_deg is not None else self.config.max_step_deg
        tilt_max_step = self.config.tilt_max_step_deg if self.config.tilt_max_step_deg is not None else self.config.max_step_deg
        pan_smoothing = self.config.pan_smoothing if self.config.pan_smoothing is not None else self.config.smoothing
        tilt_smoothing = self.config.tilt_smoothing if self.config.tilt_smoothing is not None else self.config.smoothing

        err_x = self._apply_deadzone(err_x, pan_deadzone)
        err_y = self._apply_tilt_settle_filter(err_y, frame_height)
        err_y = self._apply_tilt_hold_hysteresis(err_y, tilt_deadzone)
        err_y = self._apply_deadzone(err_y, tilt_deadzone)

        if err_x == 0.0:
            err_x = 0.0
            self.pan_axis.integral = 0.0
            self.pan_axis.prev_error = 0.0
        if err_y == 0.0:
            err_y = 0.0
            self.tilt_axis.integral = 0.0
            self.tilt_axis.prev_error = 0.0
        raw_pan = self.current_pan + self.config.pan_direction * self.pan_axis.update(err_x, dt)
        raw_tilt = self.current_tilt + self.config.tilt_direction * self.tilt_axis.update(err_y, dt)

        limited_pan = self._limit_step(raw_pan, self.current_pan, pan_max_step)
        limited_tilt = self._limit_step(raw_tilt, self.current_tilt, tilt_max_step)

        next_pan = self.current_pan * pan_smoothing + limited_pan * (1.0 - pan_smoothing)
        next_tilt = self.current_tilt * tilt_smoothing + limited_tilt * (1.0 - tilt_smoothing)

        next_pan = max(self.config.pan_min, min(self.config.pan_max, next_pan))
        next_tilt = max(self.config.tilt_min, min(self.config.tilt_max, next_tilt))

        # Servos can chatter when visual noise produces sub-degree commands.
        if abs(next_pan - self.current_pan) < pan_min_delta:
            next_pan = self.current_pan
        if abs(next_tilt - self.current_tilt) < tilt_min_delta:
            next_tilt = self.current_tilt

        moved_tilt = abs(next_tilt - self.current_tilt) >= tilt_min_delta
        self.current_pan = next_pan
        self.current_tilt = next_tilt
        if moved_tilt:
            self.tilt_settle_remaining = max(0, int(self.config.tilt_settle_frames))
        return ControlOutput(next_pan=next_pan, next_tilt=next_tilt, err_x=err_x, err_y=err_y)
