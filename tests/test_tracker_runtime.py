from __future__ import annotations

import os
import sys
import unittest

import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_ROOT = os.path.join(PROJECT_ROOT, "src")
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

from orangepi_tracker.config import TrackerConfig, default_color_presets, load_config
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

    def test_red_dominance_fallback_detects_dim_red_target(self) -> None:
        frame = np.zeros((120, 160, 3), dtype=np.uint8)
        frame[40:80, 55:105] = (35, 45, 120)
        detection = self.tracker.detect(frame)
        self.assertTrue(detection.found)
        self.assertGreaterEqual(detection.area, self.config.min_area)

    def test_rejects_sparse_color_noise_that_is_not_a_solid_note(self) -> None:
        self.tracker.set_color("blue")
        frame = np.zeros((120, 160, 3), dtype=np.uint8)
        for y in range(30, 90, 8):
            for x in range(40, 120, 8):
                frame[y : y + 3, x : x + 3] = (255, 0, 0)

        detection = self.tracker.detect(frame)

        self.assertFalse(detection.found)

    def test_prefers_continuous_target_over_far_background_patch(self) -> None:
        self.tracker.set_color("blue")
        first = np.zeros((120, 160, 3), dtype=np.uint8)
        first[42:78, 48:88] = (255, 0, 0)
        detection = self.tracker.detect(first)
        self.assertTrue(detection.found)

        second = np.zeros((120, 160, 3), dtype=np.uint8)
        second[44:80, 50:90] = (255, 0, 0)
        second[15:75, 112:158] = (255, 0, 0)
        detection = self.tracker.detect(second)

        self.assertTrue(detection.found)
        self.assertLess(detection.center_x, 100)

    def test_brief_dropout_keeps_last_square_note_detection(self) -> None:
        self.tracker.set_color("blue")
        self.config.lost_hold_frames = 3
        frame = np.zeros((120, 160, 3), dtype=np.uint8)
        frame[42:82, 58:98] = (255, 0, 0)
        first = self.tracker.detect(frame)
        self.assertTrue(first.found)

        blank = np.zeros_like(frame)
        held = self.tracker.detect(blank)

        self.assertTrue(held.found)
        self.assertEqual(held.bbox, first.bbox)
        self.assertLess(held.confidence, first.confidence)

    def test_clears_detection_after_repeated_dropout(self) -> None:
        self.tracker.set_color("blue")
        self.config.lost_hold_frames = 2
        frame = np.zeros((120, 160, 3), dtype=np.uint8)
        frame[42:82, 58:98] = (255, 0, 0)
        self.assertTrue(self.tracker.detect(frame).found)

        blank = np.zeros_like(frame)
        self.assertTrue(self.tracker.detect(blank).found)
        self.assertTrue(self.tracker.detect(blank).found)
        lost = self.tracker.detect(blank)

        self.assertFalse(lost.found)

    def test_square_note_beats_larger_elongated_same_color_patch(self) -> None:
        self.tracker.set_color("blue")
        frame = np.zeros((160, 220, 3), dtype=np.uint8)
        frame[55:105, 45:95] = (255, 0, 0)
        frame[30:70, 135:215] = (255, 0, 0)

        detection = self.tracker.detect(frame)

        self.assertTrue(detection.found)
        self.assertLess(detection.center_x, 120)

    def test_rotated_square_note_is_not_rejected_by_axis_aligned_fill_ratio(self) -> None:
        self.tracker.set_color("blue")
        self.config.min_rect_fill_ratio = 0.58
        frame = np.zeros((140, 180, 3), dtype=np.uint8)
        diamond = np.array([[90, 35], [125, 70], [90, 105], [55, 70]], dtype=np.int32)
        import cv2

        cv2.fillConvexPoly(frame, diamond, (255, 0, 0))

        detection = self.tracker.detect(frame)

        self.assertTrue(detection.found)
        self.assertAlmostEqual(detection.center_x, 90, delta=3)
        self.assertAlmostEqual(detection.center_y, 70, delta=3)

    def test_bbox_is_smoothed_for_small_edge_noise(self) -> None:
        self.tracker.set_color("blue")
        first = np.zeros((120, 160, 3), dtype=np.uint8)
        first[42:82, 58:98] = (255, 0, 0)
        first_detection = self.tracker.detect(first)

        second = np.zeros((120, 160, 3), dtype=np.uint8)
        second[44:84, 60:100] = (255, 0, 0)
        second_detection = self.tracker.detect(second)

        self.assertTrue(first_detection.found)
        self.assertTrue(second_detection.found)
        self.assertLess(second_detection.bbox[0], 60)
        self.assertLess(second_detection.bbox[1], 44)

    def test_adaptive_hsv_keeps_tracking_same_card_when_brightness_changes(self) -> None:
        self.tracker.set_color("blue")
        bright = np.zeros((120, 160, 3), dtype=np.uint8)
        bright[42:82, 58:98] = (255, 0, 0)
        first = self.tracker.detect(bright)
        self.assertTrue(first.found)

        darker = np.zeros_like(bright)
        darker[44:84, 60:100] = (105, 0, 0)
        second = self.tracker.detect(darker)

        self.assertTrue(second.found)
        self.assertGreaterEqual(second.confidence, 0.5)

    def test_center_calibration_survives_smaller_darker_sticky_note(self) -> None:
        self.config.min_area = 80
        self.config.morph_kernel = 3
        self.config.adaptive_hsv_enabled = True
        calibration = np.zeros((160, 200, 3), dtype=np.uint8)
        calibration[60:100, 80:120] = (0, 180, 255)
        self.tracker.calibrate_from_frame(calibration, roi_size=56)

        farther = np.zeros_like(calibration)
        farther[69:93, 88:112] = (0, 95, 160)
        detection = self.tracker.detect(farther)

        self.assertTrue(detection.found)
        self.assertAlmostEqual(detection.center_x, 100, delta=4)
        self.assertAlmostEqual(detection.center_y, 81, delta=4)

    def test_default_config_uses_fixed_wide_hsv_after_calibration(self) -> None:
        config = load_config(os.path.join(PROJECT_ROOT, "configs", "default_config.json"))
        tracker = HSVColorTracker(config.tracker)
        frame = np.zeros((160, 200, 3), dtype=np.uint8)
        frame[60:100, 80:120] = (0, 180, 255)

        ranges = tracker.calibrate_from_frame(frame, roi_size=56)

        self.assertFalse(config.tracker.adaptive_hsv_enabled)
        self.assertGreaterEqual(config.tracker.adaptive_hue_margin, 18)
        self.assertGreaterEqual(config.tracker.adaptive_sv_margin, 105)
        self.assertTrue(any((item["upper"][0] - item["lower"][0]) >= 18 for item in ranges))


if __name__ == "__main__":
    unittest.main()
