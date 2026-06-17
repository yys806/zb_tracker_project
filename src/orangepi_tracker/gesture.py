from __future__ import annotations

from dataclasses import dataclass
import math

import cv2
import numpy as np

from .config import GestureConfig
from .types import GestureDetection


@dataclass
class GestureRecognizer:
    config: GestureConfig

    HAND_CONNECTIONS = (
        (0, 1), (1, 2), (2, 3), (3, 4),
        (0, 5), (5, 6), (6, 7), (7, 8),
        (5, 9), (9, 10), (10, 11), (11, 12),
        (9, 13), (13, 14), (14, 15), (15, 16),
        (13, 17), (17, 18), (18, 19), (19, 20),
        (0, 17),
    )

    def __post_init__(self) -> None:
        self._last_label = "none"
        self._last_finger_count = 0
        self._stable_frames = 0
        self._frame_index = 0
        self._last_detection = GestureDetection(enabled=self.config.enabled)
        self._mp_hands = None
        self._mp_available = False
        self._mp_error: str | None = None
        self._init_mediapipe()

    def set_enabled(self, enabled: bool) -> None:
        self.config.enabled = bool(enabled)
        if not self.config.enabled:
            self.reset()

    def reset(self) -> None:
        self._last_label = "none"
        self._last_finger_count = 0
        self._stable_frames = 0

    def detect(self, frame: np.ndarray) -> GestureDetection:
        if not self.config.enabled:
            return GestureDetection(enabled=False)
        if self._should_use_mediapipe():
            detection = self._detect_mediapipe(frame)
            if detection is not None:
                self._last_detection = detection
                return detection

        mask = self._skin_mask(frame)
        contour = self._largest_hand_contour(mask, frame.shape[0] * frame.shape[1])
        if contour is None:
            self._stable_frames = 0
            detection = GestureDetection(enabled=True, backend=self._active_backend_name())
            self._last_detection = detection
            return detection

        area = float(cv2.contourArea(contour))
        x, y, w, h = cv2.boundingRect(contour)
        moments = cv2.moments(contour)
        if moments["m00"]:
            center_x = int(round(moments["m10"] / moments["m00"]))
            center_y = int(round(moments["m01"] / moments["m00"]))
        else:
            center_x = x + w // 2
            center_y = y + h // 2

        hull = cv2.convexHull(contour)
        hull_area = float(cv2.contourArea(hull))
        solidity = area / hull_area if hull_area > 1.0 else 0.0
        extent = area / float(max(w * h, 1))
        defects = self._count_convexity_defects(contour)
        finger_count = self._estimate_fingers(defects, solidity, extent)
        label = self._label_for_fingers(finger_count, solidity, extent)
        confidence = self._confidence(area, frame.shape[0] * frame.shape[1], solidity, extent, defects)

        label, finger_count = self._stabilize(label, finger_count)
        detection = GestureDetection(
            enabled=True,
            found=True,
            label=label,
            finger_count=finger_count,
            backend="traditional",
            center_x=center_x,
            center_y=center_y,
            bbox=(x, y, w, h),
            area=area,
            confidence=confidence,
            defects=defects,
            solidity=solidity,
            extent=extent,
        )
        self._last_detection = detection
        return detection

    def _init_mediapipe(self) -> None:
        backend = str(getattr(self.config, "backend", "auto")).lower()
        if backend == "traditional":
            return
        try:
            import mediapipe as mp

            self._mp_hands = mp.solutions.hands.Hands(
                static_image_mode=False,
                max_num_hands=1,
                model_complexity=int(self.config.mediapipe_model_complexity),
                min_detection_confidence=float(self.config.mediapipe_min_detection_confidence),
                min_tracking_confidence=float(self.config.mediapipe_min_tracking_confidence),
            )
            self._mp_available = True
        except Exception as exc:
            self._mp_error = str(exc)
            self._mp_hands = None
            self._mp_available = False

    def _should_use_mediapipe(self) -> bool:
        backend = str(getattr(self.config, "backend", "auto")).lower()
        return backend in {"auto", "mediapipe"} and self._mp_available and self._mp_hands is not None

    def _active_backend_name(self) -> str:
        backend = str(getattr(self.config, "backend", "auto")).lower()
        if backend == "mediapipe" and not self._mp_available:
            return "mediapipe_unavailable"
        if self._should_use_mediapipe():
            return "mediapipe"
        return "traditional"

    def _detect_mediapipe(self, frame: np.ndarray) -> GestureDetection | None:
        self._frame_index += 1
        process_every = max(1, int(self.config.mediapipe_process_every_n))
        if self._last_detection.found and self._frame_index % process_every != 0:
            return self._last_detection

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        result = self._mp_hands.process(rgb)
        if not result.multi_hand_landmarks:
            self._stable_frames = 0
            return GestureDetection(enabled=True, backend="mediapipe")

        landmarks = result.multi_hand_landmarks[0].landmark
        height, width = frame.shape[:2]
        points = [(int(round(lm.x * width)), int(round(lm.y * height))) for lm in landmarks]
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        x1 = max(0, min(xs))
        y1 = max(0, min(ys))
        x2 = min(width - 1, max(xs))
        y2 = min(height - 1, max(ys))
        bbox = (x1, y1, max(1, x2 - x1), max(1, y2 - y1))
        center_x = int(round(sum(xs) / len(xs)))
        center_y = int(round(sum(ys) / len(ys)))
        finger_states = self._mediapipe_finger_states(points)
        finger_count = sum(1 for item in finger_states if item)
        label = self._classify_mediapipe_gesture(points, finger_states)
        label, finger_count = self._stabilize(label, finger_count)
        confidence = self._mediapipe_confidence(result)
        return GestureDetection(
            enabled=True,
            found=True,
            label=label,
            finger_count=finger_count,
            backend="mediapipe",
            center_x=center_x,
            center_y=center_y,
            bbox=bbox,
            area=float(bbox[2] * bbox[3]),
            confidence=confidence,
            defects=max(0, finger_count - 1),
            solidity=0.0,
            extent=0.0,
            landmarks=points,
            connections=list(self.HAND_CONNECTIONS),
        )

    def _mediapipe_finger_states(self, points: list[tuple[int, int]]) -> list[bool]:
        if len(points) < 21:
            return [False, False, False, False, False]
        wrist_x, wrist_y = points[0]
        middle_mcp_y = points[9][1]
        palm_height = max(25.0, abs(float(wrist_y - middle_mcp_y)) * 1.5)
        vertical = abs(wrist_y - middle_mcp_y) >= abs(wrist_x - points[9][0])

        states: list[bool] = []
        if vertical:
            thumb_tip = points[4]
            thumb_ip = points[3]
            thumb_mcp = points[2]
            index_mcp = points[5]
            pinky_mcp = points[17]
            palm_mid_x = (index_mcp[0] + pinky_mcp[0]) / 2.0
            thumb_side = -1.0 if thumb_mcp[0] < palm_mid_x else 1.0
            tip_side_distance = (thumb_tip[0] - thumb_mcp[0]) * thumb_side
            ip_side_distance = (thumb_ip[0] - thumb_mcp[0]) * thumb_side
            tip_is_outside_palm = (thumb_tip[0] - palm_mid_x) * thumb_side > palm_height * 0.18
            thumb_extended = (
                tip_side_distance > max(palm_height * 0.28, ip_side_distance + palm_height * 0.08)
                and abs(thumb_tip[1] - thumb_mcp[1]) < palm_height * 0.72
                and thumb_tip[1] <= thumb_mcp[1] + palm_height * 0.18
                and tip_is_outside_palm
            )
            states.append(bool(thumb_extended))
            for tip, pip in [(8, 6), (12, 10), (16, 14), (20, 18)]:
                states.append(points[tip][1] < points[pip][1] - palm_height * 0.06)
        else:
            thumb_tip = points[4]
            thumb_mcp = points[2]
            thumb_extended = abs(thumb_tip[0] - wrist_x) > abs(thumb_mcp[0] - wrist_x) + palm_height * 0.10
            states.append(bool(thumb_extended))
            for tip, pip in [(8, 6), (12, 10), (16, 14), (20, 18)]:
                states.append(abs(points[tip][0] - wrist_x) > abs(points[pip][0] - wrist_x) + palm_height * 0.05)
        return states

    def _classify_mediapipe_gesture(self, points: list[tuple[int, int]], finger_states: list[bool]) -> str:
        if len(points) < 21 or len(finger_states) < 5:
            return "none"
        thumb, index, middle, ring, pinky = finger_states[:5]
        finger_count = sum(1 for item in finger_states if item)

        thumb_index = self._distance(points[4], points[8])
        thumb_middle = self._distance(points[4], points[12])
        index_middle = self._distance(points[8], points[12])
        palm_scale = self._palm_scale(points)

        if thumb_index < palm_scale * 0.36 and middle and ring and pinky:
            return "ok"
        if thumb_index < palm_scale * 0.42 and thumb_middle < palm_scale * 0.45 and index_middle < palm_scale * 0.38 and not ring and not pinky:
            return "seven"
        if thumb and pinky and not index and not middle and not ring:
            return "six"
        if thumb and index and not middle and not ring and not pinky:
            return "eight"
        if index and middle and ring and pinky and self._thumb_partly_open_for_five(points):
            return "five"
        if finger_count == 5:
            return "five"
        return self._label_for_fingers(finger_count, solidity=0.0, extent=0.0)

    def _thumb_partly_open_for_five(self, points: list[tuple[int, int]]) -> bool:
        if len(points) < 18:
            return False
        wrist = points[0]
        thumb_mcp = points[2]
        thumb_tip = points[4]
        middle_mcp = points[9]
        vertical = abs(wrist[1] - middle_mcp[1]) >= abs(wrist[0] - middle_mcp[0])
        if vertical:
            return thumb_tip[1] < (wrist[1] + thumb_mcp[1]) / 2.0
        return abs(thumb_tip[0] - wrist[0]) > abs(thumb_mcp[0] - wrist[0]) + self._palm_scale(points) * 0.02

    def _palm_scale(self, points: list[tuple[int, int]]) -> float:
        if len(points) < 18:
            return 80.0
        wrist = points[0]
        middle_mcp = points[9]
        index_mcp = points[5]
        pinky_mcp = points[17]
        return max(30.0, self._distance(wrist, middle_mcp), self._distance(index_mcp, pinky_mcp) * 1.35)

    @staticmethod
    def _distance(a: tuple[int, int], b: tuple[int, int]) -> float:
        return math.hypot(float(a[0] - b[0]), float(a[1] - b[1]))
    def _mediapipe_confidence(self, result) -> float:
        handedness = getattr(result, "multi_handedness", None)
        if handedness:
            classifications = getattr(handedness[0], "classification", None)
            if classifications:
                return round(float(classifications[0].score), 3)
        return 0.8

    def _skin_mask(self, frame: np.ndarray) -> np.ndarray:
        blurred = cv2.GaussianBlur(frame, (self._odd(self.config.blur_kernel), self._odd(self.config.blur_kernel)), 0)
        ycrcb = cv2.cvtColor(blurred, cv2.COLOR_BGR2YCrCb)
        lower = np.array(self.config.skin_ycrcb_lower, dtype=np.uint8)
        upper = np.array(self.config.skin_ycrcb_upper, dtype=np.uint8)
        mask = cv2.inRange(ycrcb, lower, upper)

        hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
        hsv_lower = np.array(self.config.skin_hsv_lower, dtype=np.uint8)
        hsv_upper = np.array(self.config.skin_hsv_upper, dtype=np.uint8)
        mask = cv2.bitwise_or(mask, cv2.inRange(hsv, hsv_lower, hsv_upper))

        kernel_size = self._odd(self.config.morph_kernel)
        kernel = np.ones((kernel_size, kernel_size), dtype=np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        return mask

    def _largest_hand_contour(self, mask: np.ndarray, frame_area: int) -> np.ndarray | None:
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        best = None
        best_area = 0.0
        min_area = max(float(self.config.min_area), frame_area * float(self.config.min_area_ratio))
        max_area = frame_area * float(self.config.max_area_ratio)
        for contour in contours:
            area = float(cv2.contourArea(contour))
            if area < min_area or area > max_area:
                continue
            x, y, w, h = cv2.boundingRect(contour)
            if w <= 8 or h <= 8:
                continue
            aspect = w / float(h)
            if aspect < 0.35 or aspect > 2.6:
                continue
            if area > best_area:
                best = contour
                best_area = area
        return best

    def _count_convexity_defects(self, contour: np.ndarray) -> int:
        if len(contour) < 5:
            return 0
        hull_indices = cv2.convexHull(contour, returnPoints=False)
        if hull_indices is None or len(hull_indices) < 4:
            return 0
        defects = cv2.convexityDefects(contour, hull_indices)
        if defects is None:
            return 0

        count = 0
        for defect in defects[:, 0, :]:
            start_idx, end_idx, far_idx, depth_raw = defect
            start = contour[start_idx][0]
            end = contour[end_idx][0]
            far = contour[far_idx][0]
            depth = depth_raw / 256.0
            if depth < float(self.config.min_defect_depth):
                continue
            angle = self._angle(start, far, end)
            if angle <= float(self.config.max_defect_angle_deg):
                count += 1
        return count

    def _estimate_fingers(self, defects: int, solidity: float, extent: float) -> int:
        if defects <= 0:
            if solidity >= 0.86 and extent >= 0.45:
                return 0
            return 1
        return max(1, min(5, defects + 1))

    def _label_for_fingers(self, finger_count: int, solidity: float, extent: float) -> str:
        if finger_count <= 0:
            return "fist"
        if finger_count >= 5:
            return "open_palm"
        if finger_count == 1:
            return "one"
        if finger_count == 2:
            return "two"
        if finger_count == 3:
            return "three"
        return "four"

    def _confidence(self, area: float, frame_area: int, solidity: float, extent: float, defects: int) -> float:
        area_score = min(1.0, area / max(float(self.config.min_area) * 3.0, 1.0))
        shape_score = max(0.0, min(1.0, 1.0 - abs(solidity - 0.78) * 1.4))
        extent_score = max(0.0, min(1.0, extent / 0.55))
        defect_score = min(1.0, 0.45 + defects * 0.15)
        confidence = 0.35 * area_score + 0.25 * shape_score + 0.20 * extent_score + 0.20 * defect_score
        if area > frame_area * float(self.config.max_area_ratio):
            confidence *= 0.5
        return round(max(0.0, min(1.0, confidence)), 3)

    def _stabilize(self, label: str, finger_count: int) -> tuple[str, int]:
        stable_needed = max(1, int(self.config.stable_frames))
        if label == self._last_label and finger_count == self._last_finger_count:
            self._stable_frames = min(stable_needed, self._stable_frames + 1)
            return label, finger_count
        if self._stable_frames >= stable_needed:
            self._last_label = label
            self._last_finger_count = finger_count
            self._stable_frames = 1
            return label, finger_count
        self._stable_frames += 1
        if self._last_label == "none":
            self._last_label = label
            self._last_finger_count = finger_count
            return label, finger_count
        return self._last_label, self._last_finger_count

    @staticmethod
    def _angle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
        ba = a.astype(np.float32) - b.astype(np.float32)
        bc = c.astype(np.float32) - b.astype(np.float32)
        denom = float(np.linalg.norm(ba) * np.linalg.norm(bc))
        if denom <= 1e-6:
            return 180.0
        cosine = float(np.dot(ba, bc) / denom)
        cosine = max(-1.0, min(1.0, cosine))
        return math.degrees(math.acos(cosine))

    @staticmethod
    def _odd(value: int) -> int:
        value = max(1, int(value))
        return value if value % 2 == 1 else value + 1
