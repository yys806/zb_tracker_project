from __future__ import annotations

import cv2
import numpy as np

from .types import ControlOutput, FlowMetrics, GestureDetection, TargetDetection


def draw_overlay(
    frame: np.ndarray,
    detection: TargetDetection,
    state: str,
    pan: float,
    tilt: float,
    fps: float,
    control: ControlOutput | None,
    flow: FlowMetrics | None = None,
    gesture: GestureDetection | None = None,
) -> np.ndarray:
    output = frame.copy()
    h, w = output.shape[:2]
    cv2.line(output, (w // 2, 0), (w // 2, h), (255, 255, 255), 1)
    cv2.line(output, (0, h // 2), (w, h // 2), (255, 255, 255), 1)

    if detection.found and detection.bbox is not None:
        x, y, bw, bh = detection.bbox
        cv2.rectangle(output, (x, y), (x + bw, y + bh), (0, 255, 0), 2)
        cv2.circle(output, (detection.center_x, detection.center_y), 5, (0, 255, 255), -1)
        cv2.putText(output, f"area={detection.area:.0f} conf={detection.confidence:.2f}", (x, max(20, y - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA)

    if gesture is not None and gesture.enabled and gesture.found and gesture.bbox is not None:
        gx, gy, gw, gh = gesture.bbox
        cv2.rectangle(output, (gx, gy), (gx + gw, gy + gh), (255, 170, 40), 2)
        cv2.circle(output, (gesture.center_x, gesture.center_y), 5, (255, 220, 80), -1)
        cv2.putText(
            output,
            f"gesture={gesture.label} fingers={gesture.finger_count} conf={gesture.confidence:.2f}",
            (gx, min(h - 12, gy + gh + 20)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.52,
            (255, 220, 80),
            2,
            cv2.LINE_AA,
        )

    cv2.putText(output, f"state={state}", (12, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (30, 255, 30), 2, cv2.LINE_AA)
    cv2.putText(output, f"fps={fps:.1f}", (12, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2, cv2.LINE_AA)
    cv2.putText(output, f"pan={pan:.1f} tilt={tilt:.1f}", (12, 76), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 200, 0), 2, cv2.LINE_AA)

    if control is not None:
        cv2.putText(output, f"eff_err=({control.err_x:.1f},{control.err_y:.1f})", (12, 102), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 2, cv2.LINE_AA)
    if flow is not None and flow.enabled:
        cv2.putText(
            output,
            f"flow mean={flow.mean_magnitude:.2f} motion={flow.motion_detected}",
            (12, 128),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.56,
            (255, 165, 80),
            2,
            cv2.LINE_AA,
        )
        if getattr(flow, "draw_vectors", False):
            for vector in flow.vectors:
                cv2.arrowedLine(
                    output,
                    (vector.start_x, vector.start_y),
                    (vector.end_x, vector.end_y),
                    (0, 128, 255),
                    1,
                    tipLength=0.25,
                )
    if gesture is not None and gesture.enabled:
        cv2.putText(
            output,
            f"gesture={gesture.label if gesture.found else 'none'}",
            (12, 154),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.56,
            (255, 170, 40),
            2,
            cv2.LINE_AA,
        )
    return output
