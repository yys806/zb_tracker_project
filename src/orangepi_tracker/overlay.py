from __future__ import annotations

import cv2
import numpy as np

from .types import ControlOutput, TargetDetection


def draw_overlay(frame: np.ndarray, detection: TargetDetection, state: str, pan: float, tilt: float, fps: float, control: ControlOutput | None) -> np.ndarray:
    output = frame.copy()
    h, w = output.shape[:2]
    cv2.line(output, (w // 2, 0), (w // 2, h), (255, 255, 255), 1)
    cv2.line(output, (0, h // 2), (w, h // 2), (255, 255, 255), 1)

    if detection.found and detection.bbox is not None:
        x, y, bw, bh = detection.bbox
        cv2.rectangle(output, (x, y), (x + bw, y + bh), (0, 255, 0), 2)
        cv2.circle(output, (detection.center_x, detection.center_y), 5, (0, 255, 255), -1)
        cv2.putText(output, f"area={detection.area:.0f} conf={detection.confidence:.2f}", (x, max(20, y - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA)

    cv2.putText(output, f"state={state}", (12, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (30, 255, 30), 2, cv2.LINE_AA)
    cv2.putText(output, f"fps={fps:.1f}", (12, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2, cv2.LINE_AA)
    cv2.putText(output, f"pan={pan:.1f} tilt={tilt:.1f}", (12, 76), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 200, 0), 2, cv2.LINE_AA)

    if control is not None:
        cv2.putText(output, f"err=({control.err_x:.1f},{control.err_y:.1f})", (12, 102), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 2, cv2.LINE_AA)
    return output

