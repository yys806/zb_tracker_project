from __future__ import annotations

import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_ROOT = os.path.join(PROJECT_ROOT, "src")
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

from orangepi_tracker.config import ControlConfig
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
        self.assertGreaterEqual(out.next_tilt, self.config.tilt_min)


if __name__ == "__main__":
    unittest.main()
