from __future__ import annotations

import os
import sys
import unittest

import cv2
import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_ROOT = os.path.join(PROJECT_ROOT, "src")
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

from orangepi_tracker.config import GestureConfig
from orangepi_tracker.gesture import GestureRecognizer


class GestureRecognizerTests(unittest.TestCase):
    def test_disabled_recognizer_returns_disabled_status(self) -> None:
        recognizer = GestureRecognizer(GestureConfig(enabled=False))
        frame = np.zeros((120, 160, 3), dtype=np.uint8)

        detection = recognizer.detect(frame)

        self.assertFalse(detection.enabled)
        self.assertFalse(detection.found)

    def test_detects_skin_colored_blob_as_hand_candidate(self) -> None:
        config = GestureConfig(enabled=True, min_area=200, min_area_ratio=0.0, stable_frames=1)
        recognizer = GestureRecognizer(config)
        frame = np.zeros((160, 200, 3), dtype=np.uint8)
        cv2.circle(frame, (100, 86), 34, (80, 120, 190), -1)

        detection = recognizer.detect(frame)

        self.assertTrue(detection.enabled)
        self.assertTrue(detection.found)
        self.assertIn(detection.label, {"fist", "one", "two", "three", "four", "open_palm"})
        self.assertGreater(detection.area, 200)
        self.assertGreaterEqual(detection.confidence, 0.0)

    def test_toggle_enabled_resets_to_disabled_status(self) -> None:
        config = GestureConfig(enabled=True, min_area=200, min_area_ratio=0.0, stable_frames=1)
        recognizer = GestureRecognizer(config)
        recognizer.set_enabled(False)

        detection = recognizer.detect(np.zeros((120, 160, 3), dtype=np.uint8))

        self.assertFalse(config.enabled)
        self.assertFalse(detection.enabled)


if __name__ == "__main__":
    unittest.main()
