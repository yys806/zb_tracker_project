from __future__ import annotations

import os
import sys
import unittest

import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_ROOT = os.path.join(PROJECT_ROOT, "src")
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

from orangepi_tracker.overlay import draw_overlay
from orangepi_tracker.types import GestureDetection, TargetDetection


class OverlayTests(unittest.TestCase):
    def test_gesture_landmarks_draw_skeleton_without_bbox_rectangle(self) -> None:
        frame = np.zeros((120, 160, 3), dtype=np.uint8)
        gesture = GestureDetection(
            enabled=True,
            found=True,
            label="three",
            finger_count=3,
            backend="mediapipe",
            center_x=110,
            center_y=86,
            bbox=(90, 80, 40, 30),
            confidence=0.9,
            landmarks=[(100, 86), (115, 86), (130, 86)],
            connections=[(0, 1), (1, 2)],
        )

        output = draw_overlay(
            frame,
            TargetDetection(found=False),
            state="TRACKING",
            pan=90.0,
            tilt=90.0,
            fps=24.0,
            control=None,
            gesture=gesture,
        )

        self.assertTrue(np.any(output[86, 108] != 0), "skeleton line should be drawn between landmarks")
        self.assertTrue(np.any(output[86, 115] != 0), "landmark point should be drawn")
        self.assertTrue(np.all(output[80, 90] == 0), "gesture bbox corner should not be drawn")


if __name__ == "__main__":
    unittest.main()