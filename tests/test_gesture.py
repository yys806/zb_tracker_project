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


def synthetic_hand(extended: set[str] | None = None, pose: str | None = None) -> list[tuple[int, int]]:
    extended = extended or set()
    points = [(100, 220)] * 21
    points[0] = (100, 220)
    points[1] = (88, 185)
    points[2] = (78, 165)
    points[5] = (70, 150)
    points[9] = (100, 145)
    points[13] = (125, 150)
    points[17] = (148, 160)

    if "thumb" in extended:
        points[3] = (55, 155)
        points[4] = (35, 145)
    else:
        points[3] = (55, 158)
        points[4] = (45, 195)

    finger_specs = {
        "index": (6, 7, 8, 70),
        "middle": (10, 11, 12, 100),
        "ring": (14, 15, 16, 125),
        "pinky": (18, 19, 20, 148),
    }
    for name, (pip, dip, tip, x) in finger_specs.items():
        if name in extended:
            points[pip] = (x, 105)
            points[dip] = (x, 82)
            points[tip] = (x, 55)
        else:
            points[pip] = (x, 170)
            points[dip] = (x + 4, 184)
            points[tip] = (x + 8, 196)

    if pose == "ok":
        points[3] = (73, 105)
        points[4] = (82, 96)
        points[6] = (74, 110)
        points[7] = (78, 102)
        points[8] = (84, 98)
        for name in ("middle", "ring", "pinky"):
            pip, dip, tip, x = finger_specs[name]
            points[pip] = (x, 105)
            points[dip] = (x, 82)
            points[tip] = (x, 55)
    elif pose == "seven":
        points[3] = (86, 145)
        points[4] = (94, 136)
        points[6] = (78, 150)
        points[7] = (88, 140)
        points[8] = (98, 136)
        points[10] = (105, 150)
        points[11] = (102, 142)
        points[12] = (96, 138)
    elif pose == "nine":
        points[6] = (66, 108)
        points[7] = (68, 118)
        points[8] = (76, 138)
    elif pose == "relaxed_five":
        for name in ("index", "middle", "ring", "pinky"):
            pip, dip, tip, x = finger_specs[name]
            points[pip] = (x, 105)
            points[dip] = (x, 82)
            points[tip] = (x, 55)
        points[3] = (58, 168)
        points[4] = (50, 188)
    return points


class GestureRecognizerTests(unittest.TestCase):
    def test_disabled_recognizer_returns_disabled_status(self) -> None:
        recognizer = GestureRecognizer(GestureConfig(enabled=False))
        frame = np.zeros((120, 160, 3), dtype=np.uint8)

        detection = recognizer.detect(frame)

        self.assertFalse(detection.enabled)
        self.assertFalse(detection.found)

    def test_detects_skin_colored_blob_as_hand_candidate(self) -> None:
        config = GestureConfig(enabled=True, backend="traditional", min_area=200, min_area_ratio=0.0, stable_frames=1)
        recognizer = GestureRecognizer(config)
        frame = np.zeros((160, 200, 3), dtype=np.uint8)
        cv2.circle(frame, (100, 86), 34, (80, 120, 190), -1)

        detection = recognizer.detect(frame)

        self.assertTrue(detection.enabled)
        self.assertTrue(detection.found)
        self.assertIn(detection.label, {"fist", "one", "two", "three", "four", "open_palm"})
        self.assertGreater(detection.area, 200)
        self.assertGreaterEqual(detection.confidence, 0.0)

    def test_folded_thumb_is_not_counted_as_extra_finger(self) -> None:
        config = GestureConfig(enabled=True, backend="traditional", stable_frames=1)
        recognizer = GestureRecognizer(config)
        points = synthetic_hand({"index", "middle", "ring"})

        states = recognizer._mediapipe_finger_states(points)

        self.assertEqual(states, [False, True, True, True, False])
        self.assertEqual(sum(states), 3)

    def test_mediapipe_classifies_common_chinese_number_gestures(self) -> None:
        recognizer = GestureRecognizer(GestureConfig(enabled=True, backend="traditional", stable_frames=1))
        cases = {
            "one": synthetic_hand({"index"}),
            "two": synthetic_hand({"index", "middle"}),
            "three": synthetic_hand({"index", "middle", "ring"}),
            "four": synthetic_hand({"index", "middle", "ring", "pinky"}),
            "five": synthetic_hand({"thumb", "index", "middle", "ring", "pinky"}),
            "six": synthetic_hand({"thumb", "pinky"}),
            "eight": synthetic_hand({"thumb", "index"}),
        }

        for expected, points in cases.items():
            with self.subTest(expected=expected):
                states = recognizer._mediapipe_finger_states(points)
                self.assertEqual(recognizer._classify_mediapipe_gesture(points, states), expected)

    def test_mediapipe_classifies_ok_and_pinched_seven(self) -> None:
        recognizer = GestureRecognizer(GestureConfig(enabled=True, backend="traditional", stable_frames=1))

        ok_points = synthetic_hand(pose="ok")
        ok_states = recognizer._mediapipe_finger_states(ok_points)
        self.assertEqual(recognizer._classify_mediapipe_gesture(ok_points, ok_states), "ok")

        seven_points = synthetic_hand(pose="seven")
        seven_states = recognizer._mediapipe_finger_states(seven_points)
        self.assertEqual(recognizer._classify_mediapipe_gesture(seven_points, seven_states), "seven")

    def test_mediapipe_does_not_emit_nine_gesture(self) -> None:
        recognizer = GestureRecognizer(GestureConfig(enabled=True, backend="traditional", stable_frames=1))
        points = synthetic_hand(pose="nine")
        states = recognizer._mediapipe_finger_states(points)

        self.assertNotEqual(recognizer._classify_mediapipe_gesture(points, states), "nine")

    def test_mediapipe_classifies_relaxed_open_palm_as_five(self) -> None:
        recognizer = GestureRecognizer(GestureConfig(enabled=True, backend="traditional", stable_frames=1))
        points = synthetic_hand(pose="relaxed_five")
        states = recognizer._mediapipe_finger_states(points)

        self.assertEqual(states, [False, True, True, True, True])
        self.assertEqual(recognizer._classify_mediapipe_gesture(points, states), "five")

    def test_toggle_enabled_resets_to_disabled_status(self) -> None:
        config = GestureConfig(enabled=True, backend="traditional", min_area=200, min_area_ratio=0.0, stable_frames=1)
        recognizer = GestureRecognizer(config)
        recognizer.set_enabled(False)

        detection = recognizer.detect(np.zeros((120, 160, 3), dtype=np.uint8))

        self.assertFalse(config.enabled)
        self.assertFalse(detection.enabled)


if __name__ == "__main__":
    unittest.main()
