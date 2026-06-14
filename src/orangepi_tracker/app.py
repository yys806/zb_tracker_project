from __future__ import annotations

import os
import json
import threading
import time

import cv2
import numpy as np

from .ai_client import DeepSeekClient
from .camera import OpenCVCamera
from .config import AppConfig, save_config
from .control import GimbalController
from .flow import OpticalFlowAnalyzer
from .gesture import GestureRecognizer
from .hardware import MockPanTiltHardware, PanTiltHardware, create_hardware
from .logging_utils import TrackingLogger
from .motion import FrameQualityAnalyzer, MotionAnalyzer
from .overlay import draw_overlay
from .state_machine import TrackingState, TrackingStateMachine
from .tracker import HSVColorTracker
from .types import FlowMetrics, FrameMetrics, GestureDetection, MotionMetrics, QualityMetrics, RunSummary, TargetDetection, TimelineEvent


LOCK_HOLD_STABLE_FRAMES = 3
LOCK_HOLD_CENTER_FACTOR = 2.0
LOCK_HOLD_RELEASE_PX = 22.0
LOCK_HOLD_MOTION_PX = 6.0
SERVO_MOVE_EPSILON_DEG = 1e-4


class TrackingApplication:
    def __init__(self, config: AppConfig, config_path: str | None = None) -> None:
        self.config = config
        self.config_path = config_path
        self.camera = OpenCVCamera(config.camera)
        self.tracker = HSVColorTracker(config.tracker)
        self.gesture_recognizer = GestureRecognizer(config.gesture)
        self.controller = GimbalController(config.control)
        self.flow_analyzer = OpticalFlowAnalyzer(enabled=True, use_dense_flow=True, draw_vectors=False)
        self.motion_analyzer = MotionAnalyzer(enabled=True)
        self.quality_analyzer = FrameQualityAnalyzer(enabled=True)
        self.ai_client = DeepSeekClient()
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
        self.tracking_enabled = False
        self.color_ready = False
        self.emergency_stop = False
        self.last_raw_frame: np.ndarray | None = None
        self.last_detection = TargetDetection(found=False)
        self.last_state = TrackingState.IDLE
        self.last_fps = 0.0
        self.last_detect_ms = 0.0
        self.last_control_ms = 0.0
        self.last_flow = FlowMetrics(enabled=True)
        self.last_flow_ms = 0.0
        self.flow_vectors_visible = False
        self.last_gesture = GestureDetection(enabled=config.gesture.enabled)
        self.last_gesture_ms = 0.0
        self.last_motion = MotionMetrics(enabled=True)
        self.last_motion_ms = 0.0
        self.last_quality = QualityMetrics()
        self.last_quality_ms = 0.0
        self.event_log: list[TimelineEvent] = []
        self._last_event_target_found: bool | None = None
        self.last_err_x = 0.0
        self.last_err_y = 0.0
        self.last_message = "put the target in the center, calibrate, then click start tracking"
        self._last_console_status: dict | None = None

    def ai_configured(self) -> bool:
        return self.ai_client.configured

    def run_ai_analysis(self, kind: str) -> dict:
        with self.lock:
            status = self._build_console_status_unlocked()
        prompts = {
            "status": (
                "你是嵌入式视觉云台项目的状态解释器。"
                "根据状态数据，用中文给出当前系统状态、是否适合继续跟踪、一个最重要建议。"
            ),
            "vision": (
                "你是视觉结果解释器。"
                "根据目标检测、光流、轨迹、热力图、画面质量数据，用中文解释视觉结果含义和目标运动趋势。"
            ),
            "diagnosis": (
                "你是嵌入式视觉系统异常诊断助手。"
                "根据帧率、延迟、画面质量、事件日志和状态数据，用中文判断可能异常原因，并给出排查步骤。"
            ),
        }
        if kind not in prompts:
            raise ValueError("unknown ai analysis kind")

        payload = {
            "state": status.get("state"),
            "fps": status.get("fps"),
            "timing_ms": {
                "detect": status.get("detect_time_ms"),
                "control": status.get("control_time_ms"),
                "flow": status.get("flow_time_ms"),
                "quality": (status.get("quality") or {}).get("quality_time_ms"),
            },
            "target": {
                "found": status.get("target_found"),
                "area": status.get("area"),
                "confidence": status.get("confidence"),
                "bbox": status.get("bbox"),
                "err_x": status.get("err_x"),
                "err_y": status.get("err_y"),
            },
            "flow": status.get("flow"),
            "gesture": status.get("gesture"),
            "motion": status.get("motion"),
            "quality": status.get("quality"),
            "summary": status.get("summary"),
            "events": status.get("events"),
            "tracking_enabled": status.get("tracking_enabled"),
            "emergency_stop": status.get("emergency_stop"),
            "message": status.get("message"),
        }
        user_prompt = (
            "请基于下面 JSON 数据回答。要求：最多 5 条，短句，直接给结论；"
            "不要编造摄像头画面中未提供的信息。\n\n"
            + json.dumps(payload, ensure_ascii=False, indent=2)
        )
        content = self.ai_client.chat(prompts[kind], user_prompt)
        return {"ok": True, "kind": kind, "analysis": content, "configured": self.ai_client.configured}

    def close(self) -> None:
        try:
            should_center = False
            if not isinstance(self.hardware, MockPanTiltHardware) and not self.emergency_stop and should_center:
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

    def _reset_gimbal(self, settle: bool = False) -> None:
        target_pan = self.config.control.pan_center
        target_tilt = self.config.control.tilt_center
        self.search_direction = 1.0
        self.search_tilt_direction = 1.0
        self.search_origin = target_pan
        self.search_tilt_origin = target_tilt
        if settle:
            self.hardware.ramp_to(
                target_pan,
                target_tilt,
                step_deg=self.config.hardware.reset_step_deg,
                delay_s=self.config.hardware.reset_step_delay_s,
            )
        else:
            self.hardware.move_to(target_pan, target_tilt)
        self.controller.reset()

    def center_gimbal(self) -> None:
        with self.lock:
            was_stopped = self.emergency_stop
            self._reset_gimbal()
            self.emergency_stop = was_stopped
            self.last_message = "gimbal centered"

    def reset_gimbal(self) -> dict:
        with self.lock:
            self.tracking_enabled = False
            self.emergency_stop = True
            self._reset_state_machine()
            self._reset_hold_lock()
            self.hardware.release()
            time.sleep(0.08)
            self._reset_gimbal(settle=True)
            time.sleep(0.12)
            self.hardware.release()
            self.last_message = "reset: emergency stop enabled and gimbal moved to initial position"
            self._push_event("reset", self.last_message)
            return self.get_console_status()

    def stop_motion(self) -> None:
        with self.lock:
            self.tracking_enabled = False
            self.emergency_stop = True
            self._reset_state_machine()
            self._reset_hold_lock()
            self.last_message = "emergency stop enabled"
            self._push_event("stop", self.last_message)

    def start_tracking(self) -> dict:
        with self.lock:
            if not self.color_ready:
                raise ValueError("select a color or calibrate HSV before starting tracking")
            self.tracking_enabled = True
            self.emergency_stop = False
            self._reset_state_machine()
            self._reset_hold_lock()
            self._prime_hold_lock_from_last_detection()
            self.last_message = "tracking started"
            self._push_event("start", self.last_message)
            return self.get_console_status()

    def set_color(self, color_name: str) -> dict:
        with self.lock:
            self.tracker.set_color(color_name)
            self.color_ready = True
            self.tracking_enabled = False
            self.emergency_stop = False
            self._reset_state_machine()
            self._reset_hold_lock()
            self.last_message = f"color preset switched to {color_name}; click start tracking"
            return self.get_console_status()

    def set_hsv_ranges(self, ranges: list[dict[str, list[int]]]) -> dict:
        with self.lock:
            self.tracker.set_hsv_ranges(ranges, color_name="custom")
            self.color_ready = True
            self.tracking_enabled = False
            self.emergency_stop = False
            self._reset_state_machine()
            self._reset_hold_lock()
            self.last_message = "custom HSV range updated; click start tracking"
            return self.get_console_status()

    def calibrate_color(self) -> dict:
        with self.lock:
            if self.last_raw_frame is None:
                raise ValueError("no camera frame available for calibration")
            self.tracker.calibrate_from_frame(self.last_raw_frame)
            self.color_ready = True
            self.tracking_enabled = False
            self.emergency_stop = False
            self._reset_state_machine()
            self._reset_hold_lock()
            self.last_message = "auto calibrated from center target; click start tracking"
            self._push_event("calibrate", self.last_message)
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

    def _push_event(self, kind: str, message: str) -> None:
        self.event_log.append(TimelineEvent(timestamp=time.time(), kind=kind, message=message))
        if len(self.event_log) > 50:
            self.event_log = self.event_log[-50:]

    def _build_console_status_unlocked(self) -> dict:
        detection = self.last_detection
        flow = self.last_flow
        gesture = self.last_gesture
        frame_width = 0
        frame_height = 0
        if self.last_raw_frame is not None:
            frame_height, frame_width = self.last_raw_frame.shape[:2]
        return {
            "state": self.last_state.value,
            "fps": round(self.last_fps, 2),
            "detect_time_ms": round(self.last_detect_ms, 2),
            "control_time_ms": round(self.last_control_ms, 2),
            "flow_time_ms": round(self.last_flow_ms, 2),
            "gesture_time_ms": round(self.last_gesture_ms, 2),
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
            "adaptive_hsv_enabled": self.config.tracker.adaptive_hsv_enabled,
            "backend": self.config.tracker.backend,
            "tracking_enabled": self.tracking_enabled,
            "color_ready": self.color_ready,
            "emergency_stop": self.emergency_stop,
            "hardware": "mock" if isinstance(self.hardware, MockPanTiltHardware) else "real",
            "message": self.last_message,
            "quality": {
                "brightness": round(self.last_quality.brightness, 2),
                "contrast": round(self.last_quality.contrast, 2),
                "sharpness": round(self.last_quality.sharpness, 2),
                "blur_score": round(self.last_quality.blur_score, 4),
                "exposure_state": self.last_quality.exposure_state,
                "occlusion_ratio": round(self.last_quality.occlusion_ratio, 3),
                "frame_change": round(self.last_quality.frame_change, 3),
                "quality_time_ms": round(self.last_quality_ms, 2),
            },
            "events": [
                {"timestamp": event.timestamp, "kind": event.kind, "message": event.message}
                for event in self.event_log[-12:]
            ],
            "frame_width": frame_width,
            "frame_height": frame_height,
            "flow": {
                "enabled": flow.enabled,
                "draw_vectors": self.flow_vectors_visible,
                "has_flow": flow.has_flow,
                "motion_detected": flow.motion_detected,
                "active_points": flow.active_points,
                "total_points": flow.total_points,
                "mean_magnitude": round(flow.mean_magnitude, 3),
                "median_magnitude": round(flow.median_magnitude, 3),
                "max_magnitude": round(flow.max_magnitude, 3),
                "motion_ratio": round(flow.motion_ratio, 3),
                "mean_dx": round(flow.mean_dx, 3),
                "mean_dy": round(flow.mean_dy, 3),
                "scale": round(flow.scale, 3),
            },
            "gesture": self._gesture_payload_unlocked(gesture),
            "motion": self._motion_payload_unlocked(),
            "summary": {
                "frames": self.summary.frames,
                "found_frames": self.summary.found_frames,
                "lost_events": self.summary.lost_events,
            },
        }

    def get_console_status(self) -> dict:
        acquired = self.lock.acquire(timeout=0.05)
        if not acquired:
            if self._last_console_status is not None:
                status = dict(self._last_console_status)
                status["stale"] = True
                return status
            return {
                "state": self.last_state.value,
                "fps": 0.0,
                "detect_time_ms": 0.0,
                "control_time_ms": 0.0,
                "flow_time_ms": 0.0,
                "gesture_time_ms": 0.0,
                "err_x": 0.0,
                "err_y": 0.0,
                "pan": round(self.controller.current_pan, 2),
                "tilt": round(self.controller.current_tilt, 2),
            "target_found": False,
            "area": 0.0,
            "confidence": 0.0,
            "bbox": None,
                "color_name": self.tracker.color_name,
                "available_colors": self.tracker.available_colors(),
                "hsv_ranges": self.tracker.hsv_ranges,
                "adaptive_hsv_enabled": self.config.tracker.adaptive_hsv_enabled,
                "backend": self.config.tracker.backend,
                "tracking_enabled": self.tracking_enabled,
                "color_ready": self.color_ready,
                "emergency_stop": self.emergency_stop,
                "hardware": "mock" if isinstance(self.hardware, MockPanTiltHardware) else "real",
                "message": "status snapshot is temporarily busy",
                "motion": self._motion_payload_unlocked(),
                "gesture": self._gesture_payload_unlocked(self.last_gesture),
                "summary": {"frames": 0, "found_frames": 0, "lost_events": 0},
                "stale": True,
        }
        try:
            status = self._build_console_status_unlocked()
            status["stale"] = False
            self._last_console_status = status
            return status
        finally:
            self.lock.release()

    def _process_frame(self, frame: np.ndarray, dt: float) -> tuple[TargetDetection, TrackingState, object | None, float, float, float, float]:
        detect_start = time.perf_counter()
        detection = self.tracker.detect(frame) if self.color_ready else TargetDetection(found=False)
        detect_ms = (time.perf_counter() - detect_start) * 1000.0
        flow_start = time.perf_counter()
        flow_metrics = self.flow_analyzer.process(frame)
        flow_ms = (time.perf_counter() - flow_start) * 1000.0
        gesture_start = time.perf_counter()
        gesture = self.gesture_recognizer.detect(frame)
        gesture_ms = (time.perf_counter() - gesture_start) * 1000.0
        quality_start = time.perf_counter()
        self.last_quality = QualityMetrics(**self.quality_analyzer.update(frame))
        self.last_quality_ms = (time.perf_counter() - quality_start) * 1000.0

        control_output = None
        control_start = time.perf_counter()

        if not self.tracking_enabled or self.emergency_stop:
            state = TrackingState.IDLE
            self.was_searching = False
            self._reset_state_machine()
            self._reset_hold_lock()
        else:
            state = self.machine.update(detection.found, time.perf_counter())

        if self.tracking_enabled and not self.emergency_stop and detection.found:
            self.was_searching = False
            if not self._should_hold_lock(frame.shape[1], frame.shape[0], detection):
                before_pan = self.controller.current_pan
                before_tilt = self.controller.current_tilt
                control_output = self.controller.update(frame.shape[1], frame.shape[0], detection.center_x, detection.center_y, dt)
                if (
                    abs(control_output.next_pan - before_pan) > SERVO_MOVE_EPSILON_DEG
                    or abs(control_output.next_tilt - before_tilt) > SERVO_MOVE_EPSILON_DEG
                ):
                    self.hardware.move_to(control_output.next_pan, control_output.next_tilt)
        elif (
            self.config.state_machine.enable_search
            and self.tracking_enabled
            and not self.emergency_stop
            and state == TrackingState.SEARCH
        ):
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
        self.last_flow = flow_metrics
        self.last_flow.draw_vectors = self.flow_vectors_visible
        self.last_flow_ms = flow_ms
        self.last_gesture = gesture
        self.last_gesture_ms = gesture_ms
        motion_start = time.perf_counter()
        self.last_motion = self.motion_analyzer.update(
            frame.shape[1],
            frame.shape[0],
            detection.center_x if detection.found else None,
            detection.center_y if detection.found else None,
            time.time(),
            detection.found,
        )
        self.last_motion_ms = (time.perf_counter() - motion_start) * 1000.0
        return detection, state, control_output, detect_ms, control_ms, err_x, err_y

    def _render_display(self, frame: np.ndarray, detection: TargetDetection, state: TrackingState, fps: float, control_output) -> np.ndarray:
        if self.emergency_stop:
            state_label = f"{state.value} | STOP"
        elif not self.color_ready:
            state_label = f"{state.value} | SELECT_COLOR"
        elif not self.tracking_enabled:
            state_label = f"{state.value} | READY"
        else:
            state_label = state.value
        display = draw_overlay(
            frame=frame,
            detection=detection,
            state=state_label,
            pan=self.controller.current_pan,
            tilt=self.controller.current_tilt,
            fps=fps,
            control=control_output,
            flow=self.last_flow,
            gesture=self.last_gesture,
        )
        if self.config.ui.draw_mask_preview and detection.mask is not None:
            mask_bgr = cv2.cvtColor(detection.mask, cv2.COLOR_GRAY2BGR)
            mask_bgr = cv2.resize(mask_bgr, (display.shape[1] // 4, display.shape[0] // 4))
            display[0:mask_bgr.shape[0], 0:mask_bgr.shape[1]] = mask_bgr
        return display

    def get_flow_status(self) -> dict:
        with self.lock:
            flow = self.last_flow
            return {
                "enabled": flow.enabled,
                "draw_vectors": self.flow_vectors_visible,
                "has_flow": flow.has_flow,
                "motion_detected": flow.motion_detected,
                "active_points": flow.active_points,
                "total_points": flow.total_points,
                "mean_magnitude": round(flow.mean_magnitude, 3),
                "median_magnitude": round(flow.median_magnitude, 3),
                "max_magnitude": round(flow.max_magnitude, 3),
                "motion_ratio": round(flow.motion_ratio, 3),
                "mean_dx": round(flow.mean_dx, 3),
                "mean_dy": round(flow.mean_dy, 3),
                "scale": round(flow.scale, 3),
                "flow_time_ms": round(self.last_flow_ms, 2),
                "motion": self._motion_payload_unlocked(),
            }

    def set_flow_vectors_visible(self, visible: bool) -> dict:
        with self.lock:
            self.flow_vectors_visible = bool(visible)
            self.last_message = f"flow vectors {'enabled' if self.flow_vectors_visible else 'disabled'}"
            return self.get_console_status()

    def set_gesture_enabled(self, enabled: bool) -> dict:
        with self.lock:
            self.gesture_recognizer.set_enabled(enabled)
            self.last_gesture = GestureDetection(enabled=self.config.gesture.enabled)
            self.last_gesture_ms = 0.0
            self.last_message = f"gesture recognition {'enabled' if self.config.gesture.enabled else 'disabled'}"
            self._push_event("gesture", self.last_message)
            return self.get_console_status()

    def get_gesture_status(self) -> dict:
        with self.lock:
            payload = self._gesture_payload_unlocked(self.last_gesture)
            payload["gesture_time_ms"] = round(self.last_gesture_ms, 2)
            return payload

    def _motion_payload_unlocked(self) -> dict:
        motion = self.last_motion
        return {
            "enabled": motion.enabled,
            "has_target": motion.has_target,
            "speed_px_s": round(motion.speed_px_s, 2),
            "smoothed_speed_px_s": round(motion.smoothed_speed_px_s, 2),
            "delta_x_px": round(motion.delta_x_px, 2),
            "delta_y_px": round(motion.delta_y_px, 2),
            "heading_deg": round(motion.heading_deg, 2),
            "trajectory": [{"x": point.x, "y": point.y} for point in motion.trajectory[-120:]],
            "heatmap": motion.heatmap,
            "heatmap_rows": motion.heatmap_rows,
            "heatmap_cols": motion.heatmap_cols,
            "motion_time_ms": round(self.last_motion_ms, 2),
        }

    def _gesture_payload_unlocked(self, gesture: GestureDetection) -> dict:
        return {
            "enabled": gesture.enabled,
            "found": gesture.found,
            "label": gesture.label,
            "finger_count": gesture.finger_count,
            "backend": gesture.backend,
            "center_x": gesture.center_x,
            "center_y": gesture.center_y,
            "bbox": gesture.bbox,
            "area": round(gesture.area, 2),
            "confidence": round(gesture.confidence, 3),
            "defects": gesture.defects,
            "solidity": round(gesture.solidity, 3),
            "extent": round(gesture.extent, 3),
            "gesture_time_ms": round(self.last_gesture_ms, 2),
        }

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
        if self._last_event_target_found is None:
            self._last_event_target_found = detection.found
        elif detection.found != self._last_event_target_found:
            self._last_event_target_found = detection.found
            self._push_event("target", "target reacquired" if detection.found else "target lost")

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

    def _reset_state_machine(self) -> None:
        self.machine.state = TrackingState.IDLE
        self.machine.found_streak = 0
        self.machine.lost_streak = 0
        self.machine.lost_started_at = None
        self.was_searching = False

    def _prime_hold_lock_from_last_detection(self) -> None:
        if self.last_raw_frame is None or not self.last_detection.found:
            return
        frame_height, frame_width = self.last_raw_frame.shape[:2]
        detection = self.last_detection
        frame_center_x = frame_width / 2.0
        frame_center_y = frame_height / 2.0
        err_x = abs(detection.center_x - frame_center_x)
        err_y = abs(detection.center_y - frame_center_y)
        pan_deadzone = self.config.control.pan_deadzone_px if self.config.control.pan_deadzone_px is not None else self.config.control.deadzone_px
        tilt_deadzone = self.config.control.tilt_deadzone_px if self.config.control.tilt_deadzone_px is not None else self.config.control.deadzone_px
        if err_x <= pan_deadzone and err_y <= tilt_deadzone:
            center = (detection.center_x, detection.center_y)
            self.hold_locked = True
            self.hold_stable_frames = LOCK_HOLD_STABLE_FRAMES
            self.hold_center = center
            self.previous_detection_center = center
            self.controller.pan_axis.integral = 0.0
            self.controller.pan_axis.prev_error = 0.0
            self.controller.tilt_axis.integral = 0.0
            self.controller.tilt_axis.prev_error = 0.0

    def _should_hold_lock(self, frame_width: int, frame_height: int, detection: TargetDetection) -> bool:
        center = (detection.center_x, detection.center_y)
        frame_center_x = frame_width / 2.0
        frame_center_y = frame_height / 2.0
        err_x = abs(detection.center_x - frame_center_x)
        err_y = abs(detection.center_y - frame_center_y)
        pan_deadzone = self.config.control.pan_deadzone_px if self.config.control.pan_deadzone_px is not None else self.config.control.deadzone_px
        tilt_deadzone = self.config.control.tilt_deadzone_px if self.config.control.tilt_deadzone_px is not None else self.config.control.deadzone_px
        enter_x = max(6.0, float(pan_deadzone))
        enter_y = max(6.0, float(tilt_deadzone))
        release_x = enter_x + max(10.0, enter_x * 0.28)
        release_y = enter_y + max(10.0, enter_y * 0.45)

        if self.hold_locked:
            assert self.hold_center is not None
            moved_x = abs(center[0] - self.hold_center[0])
            moved_y = abs(center[1] - self.hold_center[1])
            motion_release_x = max(LOCK_HOLD_RELEASE_PX, release_x * 0.65)
            motion_release_y = max(LOCK_HOLD_RELEASE_PX, release_y * 0.65)
            if moved_x > motion_release_x or moved_y > motion_release_y or err_x > release_x or err_y > release_y:
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

        motion_limit_x = max(LOCK_HOLD_MOTION_PX, enter_x * 0.18)
        motion_limit_y = max(LOCK_HOLD_MOTION_PX, enter_y * 0.22)
        near_center = err_x <= enter_x and err_y <= enter_y
        barely_moving = motion_x <= motion_limit_x and motion_y <= motion_limit_y

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
