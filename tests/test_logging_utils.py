from __future__ import annotations

import csv
import os
import sys
import tempfile
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_ROOT = os.path.join(PROJECT_ROOT, "src")
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

from orangepi_tracker.logging_utils import TrackingLogger
from orangepi_tracker.types import FrameMetrics


class LoggingUtilsTests(unittest.TestCase):
    def test_frame_log_includes_vision_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            logger = TrackingLogger(tmp)
            logger.log_frame(
                FrameMetrics(
                    timestamp=1.0,
                    state="TRACKING",
                    detect_time_ms=2.0,
                    control_time_ms=0.5,
                    fps=30.0,
                    err_x=12.0,
                    err_y=-8.0,
                    pan=91.0,
                    tilt=88.0,
                    target_found=True,
                    area=900.0,
                    confidence=0.9,
                    mask_ratio=0.04,
                    bbox=(10, 20, 30, 40),
                )
            )
            logger.close()

            with open(logger.csv_path, newline="", encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))

        self.assertEqual(rows[0]["target_found"], "True")
        self.assertEqual(rows[0]["mask_ratio"], "0.04")
        self.assertEqual(rows[0]["bbox"], "(10, 20, 30, 40)")


if __name__ == "__main__":
    unittest.main()
