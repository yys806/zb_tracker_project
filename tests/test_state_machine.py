from __future__ import annotations

import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_ROOT = os.path.join(PROJECT_ROOT, "src")
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

from orangepi_tracker.config import StateMachineConfig
from orangepi_tracker.state_machine import TrackingState, TrackingStateMachine


class StateMachineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.machine = TrackingStateMachine(
            StateMachineConfig(
                lock_frames=3,
                lost_frames=2,
                search_after_seconds=1.0,
                search_step_deg=2.0,
                search_pan_span=20.0,
            )
        )

    def test_enters_tracking_after_lock_frames(self) -> None:
        now = 0.0
        self.assertEqual(self.machine.update(True, now), TrackingState.IDLE)
        self.assertEqual(self.machine.update(True, now + 0.1), TrackingState.IDLE)
        self.assertEqual(self.machine.update(True, now + 0.2), TrackingState.TRACKING)

    def test_enters_search_after_timeout(self) -> None:
        self.machine.update(True, 0.0)
        self.machine.update(True, 0.1)
        self.machine.update(True, 0.2)
        self.assertEqual(self.machine.update(False, 0.3), TrackingState.TRACKING)
        self.assertEqual(self.machine.update(False, 0.5), TrackingState.LOST_SHORT)
        self.assertEqual(self.machine.update(False, 1.5), TrackingState.SEARCH)


if __name__ == "__main__":
    unittest.main()
