from __future__ import annotations

import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_ROOT = os.path.join(PROJECT_ROOT, "src")
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

from orangepi_tracker.config import ControlConfig, load_config
from orangepi_tracker.control import GimbalController


class ControlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = ControlConfig(
            pan_center=90.0,
            tilt_center=90.0,
            pan_min=20.0,
            pan_max=160.0,
            tilt_min=30.0,
            tilt_max=150.0,
            deadzone_px=10.0,
            pan_kp=0.08,
            pan_ki=0.0,
            pan_kd=0.0,
            tilt_kp=0.08,
            tilt_ki=0.0,
            tilt_kd=0.0,
            max_step_deg=5.0,
            smoothing=0.0,
            servo_min_delta_deg=0.35,
            pan_deadzone_px=None,
            tilt_deadzone_px=None,
            pan_min_delta_deg=None,
            tilt_min_delta_deg=None,
            tilt_hold_enter_px=None,
            tilt_hold_release_px=None,
            tilt_settle_frames=0,
            tilt_settle_release_px=None,
            pan_direction=-1.0,
            tilt_direction=1.0,
        )
        self.controller = GimbalController(self.config)

    def test_deadzone_blocks_small_motion(self) -> None:
        out = self.controller.update(640, 480, 325, 240, 0.05)
        self.assertAlmostEqual(out.next_pan, 90.0)
        self.assertAlmostEqual(out.next_tilt, 90.0)

    def test_large_error_moves_pan(self) -> None:
        out = self.controller.update(640, 480, 500, 240, 0.05)
        self.assertLess(out.next_pan, 90.0)

    def test_limits_are_respected(self) -> None:
        for _ in range(50):
            out = self.controller.update(640, 480, 640, 0, 0.05)
        self.assertLessEqual(out.next_pan, self.config.pan_max)
        self.assertLessEqual(out.next_tilt, self.config.tilt_max)

    def test_sub_degree_servo_delta_is_suppressed(self) -> None:
        self.config.smoothing = 0.95
        out = self.controller.update(640, 480, 334, 240, 0.05)
        self.assertAlmostEqual(out.next_pan, 90.0)
        self.assertAlmostEqual(out.next_tilt, 90.0)

    def test_top_target_moves_tilt_toward_expected_direction(self) -> None:
        out = self.controller.update(640, 480, 320, 40, 0.05)
        self.assertLess(out.next_tilt, 90.0)

    def test_top_target_escapes_upper_tilt_limit(self) -> None:
        self.controller.current_tilt = self.config.tilt_max
        out = self.controller.update(640, 480, 320, 40, 0.05)
        self.assertLess(out.next_tilt, self.config.tilt_max)

    def test_tilt_responds_fast_to_large_vertical_error(self) -> None:
        self.config.tilt_kp = 0.22
        self.config.max_step_deg = 9.0
        self.config.smoothing = 0.15
        self.controller = GimbalController(self.config)

        out = self.controller.update(640, 480, 320, 40, 0.05)

        self.assertLessEqual(out.next_tilt, 82.5)

    def test_pan_uses_axis_specific_deadzone(self) -> None:
        self.config.pan_deadzone_px = 34.0
        out = self.controller.update(640, 480, 345, 240, 0.05)
        self.assertAlmostEqual(out.next_pan, 90.0)

    def test_tilt_can_use_larger_axis_specific_step_than_pan(self) -> None:
        self.config.max_step_deg = 4.0
        self.config.tilt_max_step_deg = 11.0
        self.controller = GimbalController(self.config)

        out = self.controller.update(640, 480, 640, 40, 0.05)

        self.assertAlmostEqual(out.next_pan, 86.0)
        self.assertAlmostEqual(out.next_tilt, 79.0)

    def test_tilt_can_use_less_smoothing_than_pan_for_faster_response(self) -> None:
        self.config.max_step_deg = 8.0
        self.config.smoothing = 0.5
        self.config.tilt_smoothing = 0.0
        self.controller = GimbalController(self.config)

        out = self.controller.update(640, 480, 320, 40, 0.05)

        self.assertAlmostEqual(out.next_tilt, 82.0)

    def test_error_just_outside_deadzone_uses_only_excess_error(self) -> None:
        self.config.tilt_deadzone_px = 20.0
        self.config.tilt_kp = 0.2
        self.config.tilt_smoothing = 0.0
        self.config.tilt_min_delta_deg = 0.1
        self.controller = GimbalController(self.config)

        out = self.controller.update(640, 480, 320, 212, 0.05)

        self.assertAlmostEqual(out.next_tilt, 88.4)

    def test_large_vertical_error_still_uses_fast_limited_step(self) -> None:
        self.config.tilt_deadzone_px = 20.0
        self.config.tilt_kp = 0.2
        self.config.tilt_max_step_deg = 7.0
        self.config.tilt_smoothing = 0.0
        self.controller = GimbalController(self.config)

        out = self.controller.update(640, 480, 320, 80, 0.05)

        self.assertAlmostEqual(out.next_tilt, 83.0)

    def test_tilt_direction_can_be_flipped_for_physical_mounting(self) -> None:
        self.config.tilt_direction = -1.0
        self.config.tilt_deadzone_px = 20.0
        self.config.tilt_kp = 0.2
        self.config.tilt_max_step_deg = 7.0
        self.config.tilt_smoothing = 0.0
        self.controller = GimbalController(self.config)

        out = self.controller.update(640, 480, 320, 80, 0.05)

        self.assertAlmostEqual(out.next_tilt, 97.0)

    def test_default_config_uses_flipped_tilt_direction_for_current_gimbal(self) -> None:
        config = load_config(os.path.join(PROJECT_ROOT, "configs", "default_config.json"))

        self.assertEqual(config.control.tilt_direction, 1.0)

    def test_default_config_top_target_decreases_tilt_angle(self) -> None:
        config = load_config(os.path.join(PROJECT_ROOT, "configs", "default_config.json"))
        controller = GimbalController(config.control)

        out = controller.update(640, 480, 320, 80, 1.0 / 30.0)

        self.assertLess(out.next_tilt, config.control.tilt_center)

    def test_default_config_uses_v17_tilt_profile(self) -> None:
        config = load_config(os.path.join(PROJECT_ROOT, "configs", "default_config.json"))

        self.assertEqual(config.control.tilt_direction, 1.0)
        self.assertAlmostEqual(config.control.tilt_kp, 0.11)
        self.assertAlmostEqual(config.control.tilt_kd, 0.0)
        self.assertAlmostEqual(config.control.tilt_max_step_deg, 3.5)
        self.assertAlmostEqual(config.control.tilt_smoothing, 0.32)
        self.assertAlmostEqual(config.control.tilt_deadzone_px, 24.0)
        self.assertAlmostEqual(config.control.tilt_min_delta_deg, 0.25)
        self.assertAlmostEqual(config.control.tilt_hold_enter_px, 26.0)
        self.assertAlmostEqual(config.control.tilt_hold_release_px, 34.0)
        self.assertEqual(config.control.tilt_settle_frames, 1)
        self.assertAlmostEqual(config.control.tilt_settle_release_px, 45.0)

    def test_default_config_uses_faster_pan_profile(self) -> None:
        config = load_config(os.path.join(PROJECT_ROOT, "configs", "default_config.json"))

        self.assertAlmostEqual(config.control.pan_kp, 0.055)
        self.assertAlmostEqual(config.control.pan_max_step_deg, 5.5)
        self.assertAlmostEqual(config.control.pan_smoothing, 0.25)
        self.assertAlmostEqual(config.control.pan_deadzone_px, 30.0)

    def test_tilt_hysteresis_holds_small_vertical_jitter_near_center(self) -> None:
        self.config.tilt_deadzone_px = 18.0
        self.config.tilt_hold_enter_px = 26.0
        self.config.tilt_hold_release_px = 44.0
        self.config.tilt_kp = 0.16
        self.config.tilt_max_step_deg = 5.0
        self.config.tilt_smoothing = 0.0
        self.config.tilt_min_delta_deg = 0.1
        self.controller = GimbalController(self.config)

        for center_y in [238, 257, 223, 261, 225, 240]:
            out = self.controller.update(640, 480, 320, center_y, 0.05)

            self.assertEqual(out.err_y, 0.0)
            self.assertAlmostEqual(out.next_tilt, 90.0)

    def test_tilt_hysteresis_releases_for_real_vertical_motion(self) -> None:
        self.config.tilt_deadzone_px = 18.0
        self.config.tilt_hold_enter_px = 26.0
        self.config.tilt_hold_release_px = 44.0
        self.config.tilt_kp = 0.16
        self.config.tilt_max_step_deg = 5.0
        self.config.tilt_smoothing = 0.0
        self.config.tilt_min_delta_deg = 0.1
        self.controller = GimbalController(self.config)

        held = self.controller.update(640, 480, 320, 258, 0.05)
        released = self.controller.update(640, 480, 320, 295, 0.05)

        self.assertEqual(held.err_y, 0.0)
        self.assertAlmostEqual(held.next_tilt, 90.0)
        self.assertGreater(released.err_y, 0.0)
        self.assertGreater(released.next_tilt, held.next_tilt)

    def test_tilt_settle_blocks_camera_shake_after_tilt_motion(self) -> None:
        self.config.tilt_deadzone_px = 12.0
        self.config.tilt_hold_enter_px = None
        self.config.tilt_hold_release_px = None
        self.config.tilt_settle_frames = 2
        self.config.tilt_settle_release_px = 70.0
        self.config.tilt_kp = 0.16
        self.config.tilt_max_step_deg = 5.0
        self.config.tilt_smoothing = 0.0
        self.config.tilt_min_delta_deg = 0.1
        self.controller = GimbalController(self.config)

        moved = self.controller.update(640, 480, 320, 120, 0.05)
        first_shake = self.controller.update(640, 480, 320, 265, 0.05)
        second_shake = self.controller.update(640, 480, 320, 260, 0.05)
        real_motion = self.controller.update(640, 480, 320, 320, 0.05)

        self.assertLess(moved.next_tilt, 90.0)
        self.assertEqual(first_shake.err_y, 0.0)
        self.assertAlmostEqual(first_shake.next_tilt, moved.next_tilt)
        self.assertEqual(second_shake.err_y, 0.0)
        self.assertAlmostEqual(second_shake.next_tilt, moved.next_tilt)
        self.assertGreater(real_motion.err_y, 0.0)
        self.assertGreater(real_motion.next_tilt, second_shake.next_tilt)

    def test_tilt_settle_ignores_repeated_reverse_jitter_after_motion(self) -> None:
        self.config.tilt_deadzone_px = 12.0
        self.config.tilt_hold_enter_px = 24.0
        self.config.tilt_hold_release_px = 36.0
        self.config.tilt_settle_frames = 3
        self.config.tilt_settle_release_px = 70.0
        self.config.tilt_kp = 0.16
        self.config.tilt_max_step_deg = 5.0
        self.config.tilt_smoothing = 0.0
        self.config.tilt_min_delta_deg = 0.1
        self.controller = GimbalController(self.config)

        moved = self.controller.update(640, 480, 320, 120, 0.05)
        jitters = [
            self.controller.update(640, 480, 320, center_y, 0.05)
            for center_y in (265, 218, 263)
        ]
        real_motion = self.controller.update(640, 480, 320, 330, 0.05)

        self.assertLess(moved.next_tilt, 90.0)
        for jitter in jitters:
            self.assertEqual(jitter.err_y, 0.0)
            self.assertAlmostEqual(jitter.next_tilt, moved.next_tilt)
        self.assertGreater(real_motion.err_y, 0.0)
        self.assertGreater(real_motion.next_tilt, moved.next_tilt)


if __name__ == "__main__":
    unittest.main()
