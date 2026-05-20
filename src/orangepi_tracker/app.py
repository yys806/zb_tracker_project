from __future__ import annotations

import os
import threading
import time

import cv2
import numpy as np

from .camera import OpenCVCamera
from .config import AppConfig, save_config
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
    def __init__(self, config: AppConfig, config_path: str | None = None) -> None:
        self.config = config
        self.config_path = config_path
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
        self.search_tilt_origin = config.control.tilt_center
        self.was_searching = False
        self.hold_locked = False
        self.hold_stable_frames = 0
        self.hold_center: tuple[int, int] | None = None
        self.previous_detection_center: tuple[int, int] | None = None
        self.last_lost_started_at: float | None = None
        self.lock = threading.RLock()
        self.emergency_stop = False
        self.last_raw_frame: np.ndarray | None = None
        self.last_detection = TargetDetection(found=False)
        self.last_state = TrackingState.IDLE
        self.last_fps = 0.0
        self.last_detect_ms = 0.0
        self.last_control_ms = 0.0
        self.last_err_x = 0.0
        self.last_err_y = 0.0
        self.last_message = "ready"

    def close(self) -> None:
        try:
            if not isinstance(self.hardware, MockPanTiltHardware) and not self.emergency_stop:
                self.center_gimbal()
        except Exception:
            pass
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

    def run_web(self, host: str, port: int, jpeg_quality: int, stream_fps: float) -> int:
        self.config.ui.show_window = False
        try:
            from .web_server import run_mjpeg_server

            return run_mjpeg_server(self, host=host, port=port, jpeg_quality=jpeg_quality, stream_fps=stream_fps)
        finally:
            self.close()

    def _reset_gimbal(self) -> None:
        self.controller.reset()
        self.search_direction = 1.0
        self.search_tilt_direction = 1.0
        self.search_origin = self.config.control.pan_center
        self.search_tilt_origin = self.config.control.tilt_center
        self.hardware.move_to(self.controller.current_pan, self.controller.current_tilt)

    def center_gimbal(self) -> None:
        with self.lock:
            was_stopped = self.emergency_stop
            self._reset_gimbal()
            self.emergency_stop = was_stopped
            self.last_message = "gimbal centered"

    def stop_motion(self) -> None:
        with self.lock:
            self.emergency_stop = True
            self._reset_hold_lock()
            self.last_message = "emergency stop enabled"

    def resume_motion(self) -> None:
        with self.lock:
            self.emergency_stop = False
            self.last_message = "tracking resumed"

    def set_color(self, color_name: str) -> dict:
        with self.lock:
            self.tracker.set_color(color_name)
            self._reset_hold_lock()
            self.last_message = f"color preset switched to {color_name}"
            return self.get_console_status()

    def set_hsv_ranges(self, ranges: list[dict[str, list[int]]]) -> dict:
        with self.lock:
            self.tracker.set_hsv_ranges(ranges, color_name="custom")
            self._reset_hold_lock()
            self.last_message = "custom HSV range updated"
            return self.get_console_status()

    def calibrate_color(self) -> dict:
        with self.lock:
            if self.last_raw_frame is None:
                raise ValueError("no camera frame available for calibration")
            self.tracker.calibrate_from_frame(self.last_raw_frame)
            self._reset_hold_lock()
            self.last_message = "HSV calibrated from center ROI"
            return self.get_console_status()

    def save_runtime_config(self) -> dict:
        with self.lock:
            if self.config_path is None:
                raise ValueError("config path is unavailable")
            save_config(self.config, self.config_path)
            sudo_uid = os.environ.get("SUDO_UID")
            sudo_gid = os.environ.get("SUDO_GID")
            if sudo_uid and sudo_gid and hasattr(os, "chown"):
                try:
                    os.chown(self.config_path, int(sudo_uid), int(sudo_gid))
                except OSError:
                    pass
            self.last_message = f"config saved to {self.config_path}"
            return self.get_console_status()

    def get_console_status(self) -> dict:
        with self.lock:
            detection = self.last_detection
            return {
                "state": self.last_state.value,
                "fps": round(self.last_fps, 2),
                "detect_time_ms": round(self.last_detect_ms, 2),
                "control_time_ms": round(self.last_control_ms, 2),
                "err_x": round(self.last_err_x, 2),
                "err_y": round(self.last_err_y, 2),
                "pan": round(self.controller.current_pan, 2),
                "tilt": round(self.controller.current_tilt, 2),
                "target_found": detection.found,
                "area": round(detection.area, 2),
                "confidence": round(detection.confidence, 3),
                "bbox": detection.bbox,
                "color_name": self.tracker.color_name,
                "available_colors": self.tracker.available_colors(),
                "hsv_ranges": self.tracker.hsv_ranges,
                "backend": self.config.tracker.backend,
                "emergency_stop": self.emergency_stop,
                "hardware": "mock" if isinstance(self.hardware, MockPanTiltHardware) else "real",
                "message": self.last_message,
                "summary": {
                    "frames": self.summary.frames,
                    "found_frames": self.summary.found_frames,
                    "lost_events": self.summary.lost_events,
                },
            }

    def _process_frame(self, frame: np.ndarray, dt: float) -> tuple[TargetDetection, TrackingState, object | None, float, float, float, float]:
        detect_start = time.perf_counter()
        detection = self.tracker.detect(frame)
        detect_ms = (time.perf_counter() - detect_start) * 1000.0

        state = self.machine.update(detection.found, time.perf_counter())
        control_output = None
        control_start = time.perf_counter()

        if self.emergency_stop:
            self.was_searching = False
            self._reset_hold_lock()
        elif state == TrackingState.TRACKING and detection.found:
            self.was_searching = False
            if not self._should_hold_lock(frame.shape[1], frame.shape[0], detection):
                control_output = self.controller.update(frame.shape[1], frame.shape[0], detection.center_x, detection.center_y, dt)
                self.hardware.move_to(control_output.next_pan, control_output.next_tilt)
        elif state == TrackingState.SEARCH:
            self._reset_hold_lock()
            if detection.found:
                self.was_searching = False
            elif not self.was_searching:
                self._begin_search()
                self.was_searching = True
            else:
                self._apply_search_motion()
        else:
            self.was_searching = False
            if not detection.found:
                self._reset_hold_lock()
        control_ms = (time.perf_counter() - control_start) * 1000.0

        if detection.found:
            err_x = float(detection.center_x - frame.shape[1] / 2.0)
            err_y = float(detection.center_y - frame.shape[0] / 2.0)
        else:
            err_x = 0.0
            err_y = 0.0
        return detection, state, control_output, detect_ms, control_ms, err_x, err_y

    def _render_display(self, frame: np.ndarray, detection: TargetDetection, state: TrackingState, fps: float, control_output) -> np.ndarray:
        display = draw_overlay(
            frame=frame,
            detection=detection,
            state=f"{state.value}{' | STOP' if self.emergency_stop else ''}",
            pan=self.controller.current_pan,
            tilt=self.controller.current_tilt,
            fps=fps,
            control=control_output,
        )
        if self.config.ui.draw_mask_preview and detection.mask is not None:
            mask_bgr = cv2.cvtColor(detection.mask, cv2.COLOR_GRAY2BGR)
            mask_bgr = cv2.resize(mask_bgr, (display.shape[1] // 4, display.shape[0] // 4))
            display[0:mask_bgr.shape[0], 0:mask_bgr.shape[1]] = mask_bgr
        return display

    def _log_frame(
        self,
        detection: TargetDetection,
        state: TrackingState,
        fps: float,
        detect_ms: float,
        control_ms: float,
        err_x: float,
        err_y: float,
    ) -> None:
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

    def _update_console_snapshot(
        self,
        detection: TargetDetection,
        state: TrackingState,
        fps: float,
        detect_ms: float,
        control_ms: float,
        err_x: float,
        err_y: float,
    ) -> None:
        self.last_detection = detection
        self.last_state = state
        self.last_fps = fps
        self.last_detect_ms = detect_ms
        self.last_control_ms = control_ms
        self.last_err_x = err_x
        self.last_err_y = err_y

    def _handle_frame(self, frame: np.ndarray) -> np.ndarray:
        with self.lock:
            self.last_raw_frame = frame.copy()
            now = time.perf_counter()
            dt = max(now - self.last_frame_time, 1.0 / max(self.config.camera.fps, 1))
            self.last_frame_time = now
            detection, state, control_output, detect_ms, control_ms, err_x, err_y = self._process_frame(frame, dt)
            fps = 1.0 / max(dt, 1e-6)
            self._log_frame(detection, state, fps, detect_ms, control_ms, err_x, err_y)
            self._update_console_snapshot(detection, state, fps, detect_ms, control_ms, err_x, err_y)
            return self._render_display(frame, detection, state, fps, control_output)

    def _begin_search(self) -> None:
        self.search_origin = self.controller.current_pan
        self.search_tilt_origin = self.controller.current_tilt
        self.search_direction = 1.0 if self.controller.current_pan <= self.config.control.pan_center else -1.0
        self.search_tilt_direction = 1.0 if self.controller.current_tilt <= self.config.control.tilt_center else -1.0

    def _apply_search_motion(self) -> None:
        step = self.config.state_machine.search_step_deg
        pan_span = max(1.0, self.config.state_machine.search_pan_span)
        tilt_span = max(1.0, pan_span / 2.0)
        min_pan = max(self.config.control.pan_min, self.search_origin - pan_span)
        max_pan = min(self.config.control.pan_max, self.search_origin + pan_span)
        min_tilt = max(self.config.control.tilt_min, self.search_tilt_origin - tilt_span)
        max_tilt = min(self.config.control.tilt_max, self.search_tilt_origin + tilt_span)

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

    def read_web_frame(self) -> tuple[bool, np.ndarray | None]:
        ok, frame = self.camera.read()
        if not ok:
            print("摄像头读取失败")
            return False, None
        return True, self._handle_frame(frame)

    def run_tracking(self) -> int:
        try:
            while True:
                ok, frame = self.camera.read()
                if not ok:
                    print("摄像头读取失败")
                    return 1
                display = self._handle_frame(frame)
                if self.config.ui.show_window:
                    cv2.imshow(self.config.ui.window_name, display)
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord("q"):
                        break
        finally:
            self.close()
        return 0
