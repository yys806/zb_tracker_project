from __future__ import annotations

import os
import time

import cv2

from .camera import OpenCVCamera
from .config import AppConfig
from .control import GimbalController
from .hardware import MockPanTiltHardware, PanTiltHardware, create_hardware
from .logging_utils import TrackingLogger
from .overlay import draw_overlay
from .state_machine import TrackingState, TrackingStateMachine
from .tracker import HSVColorTracker
from .types import FrameMetrics, RunSummary, TargetDetection


LOCK_HOLD_STABLE_FRAMES = 8
LOCK_HOLD_CENTER_FACTOR = 2.0
LOCK_HOLD_RELEASE_PX = 55.0
LOCK_HOLD_MOTION_PX = 10.0


class TrackingApplication:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.camera = OpenCVCamera(config.camera)
        self.tracker = HSVColorTracker(config.tracker)
        self.controller = GimbalController(config.control)
        self.hardware = create_hardware(config.hardware, config.control)
        self.machine = TrackingStateMachine(config.state_machine)
        self.logger = TrackingLogger(config.logging.log_dir) if config.logging.enabled else None
        self.summary = RunSummary()
        self.last_frame_time = time.perf_counter()
        self.search_direction = 1.0
        self.search_origin = config.control.pan_center
        self.search_tilt_direction = 1.0
        self.was_searching = False
        self.hold_locked = False
        self.hold_stable_frames = 0
        self.hold_center: tuple[int, int] | None = None
        self.previous_detection_center: tuple[int, int] | None = None
        self.last_lost_started_at: float | None = None

    def close(self) -> None:
        self.camera.release()
        self.hardware.shutdown()
        if self.logger is not None:
            self.logger.write_summary(self.summary)
            self.logger.close()
        if self.config.ui.show_window:
            cv2.destroyAllWindows()

    def run_camera_test(self) -> int:
        try:
            while True:
                ok, frame = self.camera.read()
                if not ok:
                    print("摄像头读取失败")
                    return 1
                if self.config.ui.show_window:
                    cv2.imshow(self.config.ui.window_name, frame)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break
        finally:
            self.close()
        return 0

    def run_servo_test(self) -> int:
        try:
            sequence = [
                (self.config.control.pan_center, self.config.control.tilt_center),
                (self.config.control.pan_min, self.config.control.tilt_center),
                (self.config.control.pan_max, self.config.control.tilt_center),
                (self.config.control.pan_center, self.config.control.tilt_min),
                (self.config.control.pan_center, self.config.control.tilt_max),
                (self.config.control.pan_center, self.config.control.tilt_center),
            ]
            for pan, tilt in sequence:
                self.hardware.move_to(pan, tilt)
                print(f"pan={pan:.1f} tilt={tilt:.1f}")
                time.sleep(1.0)
        finally:
            self.close()
        return 0

    def _reset_gimbal(self) -> None:
        self.controller.reset()
        self.search_direction = 1.0
        self.search_tilt_direction = 1.0
        self.search_origin = self.config.control.pan_center
        self.hardware.move_to(self.controller.current_pan, self.controller.current_tilt)

    def _begin_search(self) -> None:
        self.search_direction = 1.0 if self.controller.current_pan <= self.config.control.pan_center else -1.0
        self.search_tilt_direction = 1.0 if self.controller.current_tilt <= self.config.control.tilt_center else -1.0

    def _apply_search_motion(self) -> None:
        step = self.config.state_machine.search_step_deg
        min_pan = self.config.control.pan_min
        max_pan = self.config.control.pan_max
        min_tilt = self.config.control.tilt_min
        max_tilt = self.config.control.tilt_max

        next_pan = self.controller.current_pan + self.search_direction * step
        next_tilt = self.controller.current_tilt + self.search_tilt_direction * step

        if next_pan >= max_pan or next_pan <= min_pan:
            self.search_direction *= -1.0
            next_pan = max(min_pan, min(max_pan, next_pan))

        if next_tilt >= max_tilt or next_tilt <= min_tilt:
            self.search_tilt_direction *= -1.0
            next_tilt = max(min_tilt, min(max_tilt, next_tilt))

        self.controller.current_pan = next_pan
        self.controller.current_tilt = next_tilt
        self.hardware.move_to(self.controller.current_pan, self.controller.current_tilt)

    def _reset_hold_lock(self) -> None:
        self.hold_locked = False
        self.hold_stable_frames = 0
        self.hold_center = None
        self.previous_detection_center = None

    def _should_hold_lock(self, frame_width: int, frame_height: int, detection: TargetDetection) -> bool:
        center = (detection.center_x, detection.center_y)
        frame_center_x = frame_width / 2.0
        frame_center_y = frame_height / 2.0
        err_x = abs(detection.center_x - frame_center_x)
        err_y = abs(detection.center_y - frame_center_y)

        if self.hold_locked:
            assert self.hold_center is not None
            moved_x = abs(center[0] - self.hold_center[0])
            moved_y = abs(center[1] - self.hold_center[1])
            if moved_x > LOCK_HOLD_RELEASE_PX or moved_y > LOCK_HOLD_RELEASE_PX:
                self._reset_hold_lock()
                self.previous_detection_center = center
                return False
            return True

        if self.previous_detection_center is None:
            motion_x = 0.0
            motion_y = 0.0
        else:
            motion_x = abs(center[0] - self.previous_detection_center[0])
            motion_y = abs(center[1] - self.previous_detection_center[1])
        self.previous_detection_center = center

        center_limit = self.config.control.deadzone_px * LOCK_HOLD_CENTER_FACTOR
        near_center = err_x <= center_limit and err_y <= center_limit
        barely_moving = motion_x <= LOCK_HOLD_MOTION_PX and motion_y <= LOCK_HOLD_MOTION_PX

        if near_center and barely_moving:
            self.hold_stable_frames += 1
        else:
            self.hold_stable_frames = 0

        if self.hold_stable_frames >= LOCK_HOLD_STABLE_FRAMES:
            self.hold_locked = True
            self.hold_center = center
            self.controller.pan_axis.integral = 0.0
            self.controller.pan_axis.prev_error = 0.0
            self.controller.tilt_axis.integral = 0.0
            self.controller.tilt_axis.prev_error = 0.0
            return True

        return False

    def _update_summary(self, fps: float, detection: TargetDetection, err_x: float, err_y: float, state: TrackingState) -> None:
        self.summary.frames += 1
        self.summary.total_fps += fps
        self.summary.total_abs_err_x += abs(err_x)
        self.summary.total_abs_err_y += abs(err_y)
        self.summary.max_abs_err_x = max(self.summary.max_abs_err_x, abs(err_x))
        self.summary.max_abs_err_y = max(self.summary.max_abs_err_y, abs(err_y))
        if detection.found:
            self.summary.found_frames += 1
            if self.last_lost_started_at is not None:
                self.summary.reacquire_times.append(time.perf_counter() - self.last_lost_started_at)
                self.last_lost_started_at = None
        elif state == TrackingState.LOST_SHORT and self.last_lost_started_at is None:
            self.summary.lost_events += 1
            self.last_lost_started_at = time.perf_counter()

    def run_tracking(self) -> int:
        try:
            while True:
                loop_started = time.perf_counter()
                ok, frame = self.camera.read()
                if not ok:
                    print("摄像头读取失败")
                    return 1

                now = time.perf_counter()
                dt = max(now - self.last_frame_time, 1.0 / max(self.config.camera.fps, 1))
                self.last_frame_time = now

                detect_start = time.perf_counter()
                detection = self.tracker.detect(frame)
                detect_ms = (time.perf_counter() - detect_start) * 1000.0

                state = self.machine.update(detection.found, now)
                control_output = None
                control_start = time.perf_counter()

                if state == TrackingState.TRACKING and detection.found:
                    self.was_searching = False
                    if not self._should_hold_lock(frame.shape[1], frame.shape[0], detection):
                        control_output = self.controller.update(frame.shape[1], frame.shape[0], detection.center_x, detection.center_y, dt)
                        self.hardware.move_to(control_output.next_pan, control_output.next_tilt)
                elif state == TrackingState.SEARCH:
                    self._reset_hold_lock()
                    if not self.was_searching:
                        self._begin_search()
                        self.was_searching = True
                    else:
                        self._apply_search_motion()
                else:
                    self.was_searching = False
                    if not detection.found:
                        self._reset_hold_lock()
                control_ms = (time.perf_counter() - control_start) * 1000.0

                fps = 1.0 / max(time.perf_counter() - loop_started, 1e-6)
                err_x = control_output.err_x if control_output is not None else 0.0
                err_y = control_output.err_y if control_output is not None else 0.0
                self._update_summary(fps, detection, err_x, err_y, state)

                if self.logger is not None:
                    self.logger.log_frame(
                        FrameMetrics(
                            timestamp=time.time(),
                            state=state.value,
                            detect_time_ms=detect_ms,
                            control_time_ms=control_ms,
                            fps=fps,
                            err_x=err_x,
                            err_y=err_y,
                            pan=self.controller.current_pan,
                            tilt=self.controller.current_tilt,
                            target_found=detection.found,
                            area=detection.area,
                            confidence=detection.confidence,
                        )
                    )

                if self.config.ui.show_window:
                    display = draw_overlay(
                        frame=frame,
                        detection=detection,
                        state=state.value,
                        pan=self.controller.current_pan,
                        tilt=self.controller.current_tilt,
                        fps=fps,
                        control=control_output,
                    )
                    if self.config.ui.draw_mask_preview and detection.mask is not None:
                        mask_bgr = cv2.cvtColor(detection.mask, cv2.COLOR_GRAY2BGR)
                        mask_bgr = cv2.resize(mask_bgr, (display.shape[1] // 4, display.shape[0] // 4))
                        display[0:mask_bgr.shape[0], 0:mask_bgr.shape[1]] = mask_bgr
                    cv2.imshow(self.config.ui.window_name, display)
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord("q"):
                        break
        finally:
            self.close()
        return 0
