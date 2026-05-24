from __future__ import annotations

import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_ROOT = os.path.join(PROJECT_ROOT, "src")
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

from orangepi_tracker.config import ControlConfig
from orangepi_tracker.hardware import MockPanTiltHardware


class HardwareTests(unittest.TestCase):
    def make_control(self) -> ControlConfig:
        return ControlConfig(
            pan_center=90.0,
            tilt_center=90.0,
            pan_min=20.0,
            pan_max=160.0,
            tilt_min=35.0,
            tilt_max=145.0,
            deadzone_px=20.0,
            pan_kp=0.05,
            pan_ki=0.0,
            pan_kd=0.0,
            tilt_kp=0.12,
            tilt_ki=0.0,
            tilt_kd=0.0,
            max_step_deg=5.0,
            smoothing=0.0,
        )

    def test_release_marks_mock_hardware_idle(self) -> None:
        hardware = MockPanTiltHardware(self.make_control())
        hardware.move_to(120.0, 130.0)

        hardware.release()

        self.assertTrue(hardware.released)

    def test_ramp_to_limits_each_motion_step(self) -> None:
        hardware = MockPanTiltHardware(self.make_control())
        moves: list[tuple[float, float]] = []
        original_move_to = hardware.move_to

        def record_move(pan: float, tilt: float) -> None:
            original_move_to(pan, tilt)
            moves.append((hardware.pan, hardware.tilt))

        hardware.move_to = record_move
        original_move_to(130.0, 140.0)

        hardware.ramp_to(90.0, 90.0, step_deg=2.0, delay_s=0.0)

        self.assertEqual(moves[-1], (90.0, 90.0))
        for previous, current in zip(moves, moves[1:]):
            self.assertLessEqual(abs(current[0] - previous[0]), 2.1)
            self.assertLessEqual(abs(current[1] - previous[1]), 2.1)

    def test_ramp_to_eases_in_and_out_for_smoother_reset(self) -> None:
        hardware = MockPanTiltHardware(self.make_control())
        moves: list[tuple[float, float]] = []
        original_move_to = hardware.move_to

        def record_move(pan: float, tilt: float) -> None:
            original_move_to(pan, tilt)
            moves.append((hardware.pan, hardware.tilt))

        hardware.move_to = record_move
        original_move_to(130.0, 140.0)

        hardware.ramp_to(90.0, 90.0, step_deg=2.0, delay_s=0.0)

        first_step = abs(moves[1][1] - moves[0][1])
        middle_step = max(abs(current[1] - previous[1]) for previous, current in zip(moves[5:15], moves[6:16]))
        last_step = abs(moves[-1][1] - moves[-2][1])
        self.assertLess(first_step, middle_step)
        self.assertLess(last_step, middle_step)


if __name__ == "__main__":
    unittest.main()
