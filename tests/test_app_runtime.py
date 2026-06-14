from __future__ import annotations

import os
import sys
import threading
import unittest
from unittest.mock import patch

import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_ROOT = os.path.join(PROJECT_ROOT, "src")
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

from orangepi_tracker import app as app_module
from orangepi_tracker.config import (
    AppConfig,
    CameraConfig,
    ControlConfig,
    HardwareConfig,
    GestureConfig,
    LoggingConfig,
    StateMachineConfig,
    TrackerConfig,
    UIConfig,
    default_color_presets,
)
from orangepi_tracker.types import TargetDetection


class FakeCamera:
    def read(self):
        return True, np.zeros((120, 160, 3), dtype=np.uint8)

    def release(self) -> None:
        return None


class CountingHardware(app_module.MockPanTiltHardware):
    def __post_init__(self) -> None:
        super().__post_init__()
        self.moves: list[tuple[float, float]] = []

    def move_to(self, pan: float, tilt: float) -> None:
        super().move_to(pan, tilt)
        self.moves.append((self.pan, self.tilt))

    def ramp_to(self, pan: float, tilt: float, step_deg: float = 2.0, delay_s: float = 0.035) -> None:
        super().ramp_to(pan, tilt, step_deg=step_deg, delay_s=0.0)


class ApplicationRuntimeTests(unittest.TestCase):
    def make_config(self) -> AppConfig:
        presets = default_color_presets()
        return AppConfig(
            camera=CameraConfig(device_index=0, width=160, height=120, fps=30, mirror=False),
            tracker=TrackerConfig(
                backend="opencv",
                min_area=20,
                max_area_ratio=0.8,
                blur_kernel=3,
                morph_kernel=3,
                hsv_ranges=presets["red"],
                color_name="red",
                color_presets=presets,
            ),
            control=ControlConfig(
                pan_center=90.0,
                tilt_center=90.0,
                pan_min=20.0,
                pan_max=160.0,
                tilt_min=35.0,
                tilt_max=145.0,
                deadzone_px=20.0,
                pan_kp=0.08,
                pan_ki=0.0,
                pan_kd=0.006,
                tilt_kp=0.12,
                tilt_ki=0.0,
                tilt_kd=0.004,
                max_step_deg=5.0,
                smoothing=0.36,
                servo_min_delta_deg=0.25,
                pan_deadzone_px=34.0,
                tilt_deadzone_px=12.0,
                pan_min_delta_deg=0.6,
                tilt_min_delta_deg=0.1,
                pan_direction=-1.0,
                tilt_direction=1.0,
            ),
            state_machine=StateMachineConfig(
                lock_frames=3,
                lost_frames=5,
                search_after_seconds=1.2,
                search_step_deg=1.0,
                search_pan_span=28.0,
            ),
            logging=LoggingConfig(enabled=False, log_dir="logs"),
            ui=UIConfig(show_window=False, window_name="test", draw_mask_preview=False),
            gesture=GestureConfig(enabled=False, min_area=200, min_area_ratio=0.0, stable_frames=1),
            hardware=HardwareConfig(
                force_mock=True,
                i2c_address=0x40,
                pan_channel=1,
                tilt_channel=0,
                frequency_hz=50,
                min_pulse=500,
                max_pulse=2500,
            ),
        )

    def make_app(self) -> app_module.TrackingApplication:
        with patch.object(app_module, "OpenCVCamera", return_value=FakeCamera()):
            return app_module.TrackingApplication(self.make_config())

    def test_tracking_requires_explicit_color_then_start(self) -> None:
        app = self.make_app()
        self.assertFalse(app.get_console_status()["color_ready"])
        self.assertFalse(app.get_console_status()["tracking_enabled"])

        with self.assertRaises(ValueError):
            app.start_tracking()

        status = app.set_color("red")
        self.assertTrue(status["color_ready"])
        self.assertFalse(status["tracking_enabled"])

        status = app.start_tracking()
        self.assertTrue(status["tracking_enabled"])
        self.assertFalse(status["emergency_stop"])

    def test_found_target_controls_tilt_before_tracking_state_lock(self) -> None:
        app = self.make_app()
        app.config.state_machine.lock_frames = 99
        app.set_color("red")
        app.start_tracking()

        app.tracker.detect = lambda frame: TargetDetection(found=True, center_x=80, center_y=10, bbox=(70, 0, 20, 20), area=400)
        before_tilt = app.controller.current_tilt
        detection, state, control_output, *_ = app._process_frame(np.zeros((120, 160, 3), dtype=np.uint8), 1.0 / 30.0)

        self.assertTrue(detection.found)
        self.assertNotEqual(state.value, "TRACKING")
        self.assertIsNotNone(control_output)
        self.assertLess(app.controller.current_tilt, before_tilt)

    def test_found_top_target_escapes_upper_tilt_limit(self) -> None:
        app = self.make_app()
        app.set_color("red")
        app.start_tracking()
        app.controller.current_tilt = app.config.control.tilt_max

        app.tracker.detect = lambda frame: TargetDetection(found=True, center_x=80, center_y=10, bbox=(70, 0, 20, 20), area=400)
        _, _, control_output, *_ = app._process_frame(np.zeros((120, 160, 3), dtype=np.uint8), 1.0 / 30.0)

        self.assertIsNotNone(control_output)
        self.assertLess(app.controller.current_tilt, app.config.control.tilt_max)

    def test_reset_stops_tracking_and_moves_to_initial_angles(self) -> None:
        app = self.make_app()
        app.set_color("red")
        app.start_tracking()
        app.controller.current_pan = 130.0
        app.controller.current_tilt = app.config.control.tilt_min
        app.hardware.move_to(app.controller.current_pan, app.controller.current_tilt)

        status = app.reset_gimbal()

        self.assertFalse(status["tracking_enabled"])
        self.assertTrue(status["emergency_stop"])
        self.assertAlmostEqual(status["pan"], app.config.control.pan_center)
        self.assertAlmostEqual(status["tilt"], app.config.control.tilt_center)
        self.assertAlmostEqual(app.hardware.pan, app.config.control.pan_center)
        self.assertAlmostEqual(app.hardware.tilt, app.config.control.tilt_center)
        self.assertIn("reset", status["message"])

    def test_reset_repeats_initial_angle_command_for_reliable_settle(self) -> None:
        with (
            patch.object(app_module, "OpenCVCamera", return_value=FakeCamera()),
            patch.object(app_module, "create_hardware", side_effect=lambda hardware, control: CountingHardware(control)),
            patch.object(app_module.time, "sleep", return_value=None),
        ):
            app = app_module.TrackingApplication(self.make_config())

        app.set_color("red")
        app.start_tracking()
        app.controller.current_pan = 130.0
        app.controller.current_tilt = 140.0
        app.hardware.move_to(130.0, 140.0)

        app.reset_gimbal()

        center = (app.config.control.pan_center, app.config.control.tilt_center)
        self.assertEqual(app.hardware.moves[-1], center)
        self.assertGreater(len(app.hardware.moves), 3)

    def test_reset_releases_pwm_after_reaching_initial_angles(self) -> None:
        with (
            patch.object(app_module, "OpenCVCamera", return_value=FakeCamera()),
            patch.object(app_module, "create_hardware", side_effect=lambda hardware, control: CountingHardware(control)),
            patch.object(app_module.time, "sleep", return_value=None),
        ):
            app = app_module.TrackingApplication(self.make_config())

        app.set_color("red")
        app.start_tracking()
        app.controller.current_pan = 130.0
        app.controller.current_tilt = 140.0
        app.hardware.move_to(130.0, 140.0)

        status = app.reset_gimbal()

        self.assertTrue(status["emergency_stop"])
        self.assertTrue(app.hardware.released)

    def test_reset_ramps_toward_center_without_large_single_jump(self) -> None:
        with (
            patch.object(app_module, "OpenCVCamera", return_value=FakeCamera()),
            patch.object(app_module, "create_hardware", side_effect=lambda hardware, control: CountingHardware(control)),
        ):
            config = self.make_config()
            config.hardware.reset_step_deg = 2.0
            app = app_module.TrackingApplication(config)

        app.set_color("red")
        app.start_tracking()
        app.controller.current_pan = 130.0
        app.controller.current_tilt = 140.0
        app.hardware.move_to(130.0, 140.0)
        app.hardware.moves.clear()

        app.reset_gimbal()

        for previous, current in zip(app.hardware.moves, app.hardware.moves[1:]):
            self.assertLessEqual(abs(current[0] - previous[0]), 2.1)
            self.assertLessEqual(abs(current[1] - previous[1]), 2.1)

    def test_stable_near_center_target_stops_servo_chatter(self) -> None:
        with (
            patch.object(app_module, "OpenCVCamera", return_value=FakeCamera()),
            patch.object(app_module, "create_hardware", side_effect=lambda hardware, control: CountingHardware(control)),
        ):
            app = app_module.TrackingApplication(self.make_config())
        app.set_color("red")
        app.start_tracking()
        centers = [(80, 60), (81, 60), (80, 61), (81, 61), (80, 60), (82, 61)]

        def detect(_frame):
            cx, cy = centers.pop(0)
            return TargetDetection(found=True, center_x=cx, center_y=cy, bbox=(70, 50, 20, 20), area=400, confidence=1.0)

        app.tracker.detect = detect
        for _ in range(6):
            app._process_frame(np.zeros((120, 160, 3), dtype=np.uint8), 1.0 / 30.0)

        self.assertTrue(app.hold_locked)
        self.assertEqual(app.hardware.moves, [])

    def test_centered_target_does_not_reissue_identical_servo_commands(self) -> None:
        with (
            patch.object(app_module, "OpenCVCamera", return_value=FakeCamera()),
            patch.object(app_module, "create_hardware", side_effect=lambda hardware, control: CountingHardware(control)),
        ):
            app = app_module.TrackingApplication(self.make_config())
        app.set_color("red")
        app.start_tracking()
        app.tracker.detect = lambda frame: TargetDetection(
            found=True,
            center_x=80,
            center_y=60,
            bbox=(70, 50, 20, 20),
            area=400,
            confidence=1.0,
        )

        for _ in range(6):
            app._process_frame(np.zeros((120, 160, 3), dtype=np.uint8), 1.0 / 30.0)

        self.assertTrue(app.hold_locked)
        self.assertEqual(app.hardware.moves, [])

    def test_start_tracking_does_not_kick_servo_when_target_is_already_centered(self) -> None:
        with (
            patch.object(app_module, "OpenCVCamera", return_value=FakeCamera()),
            patch.object(app_module, "create_hardware", side_effect=lambda hardware, control: CountingHardware(control)),
        ):
            app = app_module.TrackingApplication(self.make_config())
        app.last_raw_frame = np.zeros((120, 160, 3), dtype=np.uint8)
        app.last_detection = TargetDetection(
            found=True,
            center_x=80,
            center_y=60,
            bbox=(70, 50, 20, 20),
            area=400,
            confidence=1.0,
        )
        app.set_color("red")
        app.start_tracking()
        app.tracker.detect = lambda frame: TargetDetection(
            found=True,
            center_x=80,
            center_y=60,
            bbox=(70, 50, 20, 20),
            area=400,
            confidence=1.0,
        )

        app._process_frame(np.zeros((120, 160, 3), dtype=np.uint8), 1.0 / 30.0)

        self.assertTrue(app.hold_locked)
        self.assertEqual(app.hardware.moves, [])

    def test_vertical_error_outside_tilt_deadzone_does_not_enter_hold_lock(self) -> None:
        with (
            patch.object(app_module, "OpenCVCamera", return_value=FakeCamera()),
            patch.object(app_module, "create_hardware", side_effect=lambda hardware, control: CountingHardware(control)),
        ):
            app = app_module.TrackingApplication(self.make_config())
        app.set_color("red")
        app.start_tracking()
        app.tracker.detect = lambda frame: TargetDetection(
            found=True,
            center_x=80,
            center_y=90,
            bbox=(70, 80, 20, 20),
            area=400,
            confidence=1.0,
        )

        for _ in range(6):
            app._process_frame(np.zeros((120, 160, 3), dtype=np.uint8), 1.0 / 30.0)

        self.assertFalse(app.hold_locked)
        self.assertGreater(len(app.hardware.moves), 3)

    def test_tilt_moves_fast_then_quiets_near_center(self) -> None:
        with (
            patch.object(app_module, "OpenCVCamera", return_value=FakeCamera()),
            patch.object(app_module, "create_hardware", side_effect=lambda hardware, control: CountingHardware(control)),
        ):
            app = app_module.TrackingApplication(self.make_config())
        app.config.control.tilt_deadzone_px = 12.0
        app.config.control.tilt_kp = 0.2
        app.config.control.tilt_max_step_deg = 7.0
        app.config.control.tilt_smoothing = 0.0
        app.config.control.tilt_min_delta_deg = 0.45
        app.controller = app_module.GimbalController(app.config.control)
        app.set_color("red")
        app.start_tracking()

        centers = [(80, 15), (80, 25), (80, 38), (80, 50), (80, 57), (80, 58), (80, 60), (80, 61)]

        def detect(_frame):
            cx, cy = centers.pop(0)
            return TargetDetection(found=True, center_x=cx, center_y=cy, bbox=(70, cy - 10, 20, 20), area=400, confidence=1.0)

        app.tracker.detect = detect
        for _ in range(8):
            app._process_frame(np.zeros((120, 160, 3), dtype=np.uint8), 1.0 / 30.0)

        tilt_moves = [tilt for _, tilt in app.hardware.moves]
        self.assertLessEqual(tilt_moves[0], 83.0)
        self.assertLess(len(app.hardware.moves), 6)
        self.assertTrue(app.hold_locked)

    def test_lost_target_holds_position_instead_of_searching_by_default(self) -> None:
        with (
            patch.object(app_module, "OpenCVCamera", return_value=FakeCamera()),
            patch.object(app_module, "create_hardware", side_effect=lambda hardware, control: CountingHardware(control)),
        ):
            app = app_module.TrackingApplication(self.make_config())
        app.last_raw_frame = np.zeros((120, 160, 3), dtype=np.uint8)
        app.last_raw_frame[45:75, 65:95] = (255, 0, 0)
        app.calibrate_color()
        app.start_tracking()
        app.tracker.detect = lambda frame: TargetDetection(found=False)

        for _ in range(12):
            app._process_frame(np.zeros((120, 160, 3), dtype=np.uint8), 0.3)

        self.assertEqual(app.hardware.moves, [])

    def test_console_status_reports_hsv_even_when_called_inside_lock(self) -> None:
        app = self.make_app()
        app.color_ready = True

        self.assertTrue(app.lock.acquire(blocking=False))
        try:
            status = app.get_console_status()
        finally:
            app.lock.release()

        self.assertIn("hsv_ranges", status)
        self.assertTrue(status["hsv_ranges"])
        self.assertEqual(status["state"], "IDLE")
        self.assertFalse(status["tracking_enabled"])

    def test_console_status_returns_cached_snapshot_when_frame_thread_is_busy(self) -> None:
        app = self.make_app()
        app.color_ready = True
        initial_status = app.get_console_status()
        result: list[dict] = []

        self.assertTrue(app.lock.acquire(blocking=False))
        try:
            worker = threading.Thread(target=lambda: result.append(app.get_console_status()))
            worker.start()
            worker.join(timeout=0.5)
            self.assertFalse(worker.is_alive())
        finally:
            app.lock.release()
            if worker.is_alive():
                worker.join(timeout=1.0)

        self.assertEqual(result[0]["hsv_ranges"], initial_status["hsv_ranges"])
        self.assertTrue(result[0]["stale"])

    def test_flow_status_is_exposed_in_console_snapshot(self) -> None:
        app = self.make_app()
        app.tracking_enabled = True
        app.last_flow.motion_detected = True
        app.last_flow.active_points = 8
        app.last_flow.total_points = 20
        app.last_flow.mean_magnitude = 2.4

        status = app.get_flow_status()
        console = app.get_console_status()

        self.assertTrue(status["motion_detected"])
        self.assertEqual(status["active_points"], 8)
        self.assertIn("flow", console)
        self.assertIn("flow_time_ms", console)
        self.assertTrue(console["flow"]["enabled"])

    def test_gesture_toggle_is_exposed_in_console_snapshot(self) -> None:
        app = self.make_app()

        initial = app.get_console_status()
        self.assertIn("gesture", initial)
        self.assertFalse(initial["gesture"]["enabled"])

        enabled = app.set_gesture_enabled(True)

        self.assertTrue(enabled["gesture"]["enabled"])
        self.assertIn("gesture recognition enabled", enabled["message"])

    def test_gesture_status_updates_when_enabled(self) -> None:
        app = self.make_app()
        app.set_gesture_enabled(True)
        frame = np.zeros((120, 160, 3), dtype=np.uint8)
        frame[35:90, 55:110] = (80, 120, 190)

        app._process_frame(frame, 1.0 / 30.0)
        status = app.get_gesture_status()

        self.assertTrue(status["enabled"])
        self.assertIn("found", status)
        self.assertIn("gesture_time_ms", status)


if __name__ == "__main__":
    unittest.main()
