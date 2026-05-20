from __future__ import annotations

import os
import sys
import unittest

import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_ROOT = os.path.join(PROJECT_ROOT, "src")
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

from orangepi_tracker.config import TrackerConfig, default_color_presets
from orangepi_tracker.tracker import HSVColorTracker


class TrackerRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = TrackerConfig(
            backend="opencv",
            min_area=20,
            max_area_ratio=0.8,
            blur_kernel=3,
            morph_kernel=3,
            hsv_ranges=default_color_presets()["red"],
            color_name="red",
            color_presets=default_color_presets(),
        )
        self.tracker = HSVColorTracker(self.config)

    def test_switches_color_preset(self) -> None:
        self.tracker.set_color("blue")
        self.assertEqual(self.tracker.color_name, "blue")
        self.assertEqual(self.tracker.hsv_ranges, default_color_presets()["blue"])

    def test_custom_hsv_ranges_are_normalized(self) -> None:
        self.tracker.set_hsv_ranges([{"lower": [120, 300, -10], "upper": [80, 10, 260]}])
        self.assertEqual(self.tracker.color_name, "custom")
        self.assertEqual(self.tracker.hsv_ranges[0]["lower"], [80, 10, 0])
        self.assertEqual(self.tracker.hsv_ranges[0]["upper"], [120, 255, 255])

    def test_calibrates_from_center_roi(self) -> None:
        frame = np.zeros((120, 160, 3), dtype=np.uint8)
        frame[45:75, 65:95] = (255, 0, 0)
        ranges = self.tracker.calibrate_from_frame(frame, roi_size=30, hue_margin=8, sv_margin=30)
        self.assertEqual(self.tracker.color_name, "custom")
        self.assertTrue(ranges)
        self.assertLessEqual(ranges[0]["lower"][0], ranges[0]["upper"][0])


if __name__ == "__main__":
    unittest.main()
