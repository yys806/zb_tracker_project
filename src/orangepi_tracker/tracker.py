from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import cv2
import numpy as np

from .config import TrackerConfig
from .types import TargetDetection


MorphologyFn = Callable[[np.ndarray, int], np.ndarray]
HSV_LIMITS = ((0, 180), (0, 255), (0, 255))


@dataclass(slots=True)
class Candidate:
    x: int
    y: int
    w: int
    h: int
    center_x: float
    center_y: float
    area: float
    fill_ratio: float
    aspect: float
    score: float


def clamp_hsv_triplet(values: list[int]) -> list[int]:
    return [max(low, min(high, int(value))) for value, (low, high) in zip(values, HSV_LIMITS)]


def normalize_hsv_range(hsv_range: dict[str, list[int]]) -> dict[str, list[int]]:
    lower = clamp_hsv_triplet(hsv_range["lower"])
    upper = clamp_hsv_triplet(hsv_range["upper"])
    return {
        "lower": [min(lv, uv) for lv, uv in zip(lower, upper)],
        "upper": [max(lv, uv) for lv, uv in zip(lower, upper)],
    }


def copy_hsv_ranges(ranges: list[dict[str, list[int]]]) -> list[dict[str, list[int]]]:
    return [normalize_hsv_range({"lower": item["lower"][:], "upper": item["upper"][:]}) for item in ranges]


def pure_python_open_close(mask: np.ndarray, kernel_size: int) -> np.ndarray:
    radius = kernel_size // 2
    height, width = mask.shape

    def erode_once(src: np.ndarray) -> np.ndarray:
        dst = np.zeros_like(src)
        for y in range(height):
            for x in range(width):
                keep = 255
                for ky in range(-radius, radius + 1):
                    for kx in range(-radius, radius + 1):
                        yy = y + ky
                        xx = x + kx
                        # Match OpenCV's morphology default: outside pixels do not
                        # shrink a white object during erosion.
                        if 0 <= yy < height and 0 <= xx < width and src[yy, xx] == 0:
                            keep = 0
                            break
                    if keep == 0:
                        break
                dst[y, x] = keep
        return dst

    def dilate_once(src: np.ndarray) -> np.ndarray:
        dst = np.zeros_like(src)
        for y in range(height):
            for x in range(width):
                value = 0
                for ky in range(-radius, radius + 1):
                    for kx in range(-radius, radius + 1):
                        yy = y + ky
                        xx = x + kx
                        if 0 <= yy < height and 0 <= xx < width and src[yy, xx] > 0:
                            value = 255
                            break
                    if value == 255:
                        break
                dst[y, x] = value
        return dst

    opened = dilate_once(erode_once(mask))
    return erode_once(dilate_once(opened))


def pymp_open_close(mask: np.ndarray, kernel_size: int) -> np.ndarray:
    import pymp

    radius = kernel_size // 2
    height, width = mask.shape

    def erode_once(src: np.ndarray) -> np.ndarray:
        dst = pymp.shared.array(mask.shape, dtype=np.uint8)
        with pymp.Parallel() as parallel:
            for y in parallel.range(height):
                for x in range(width):
                    keep = 255
                    for ky in range(-radius, radius + 1):
                        for kx in range(-radius, radius + 1):
                            yy = y + ky
                            xx = x + kx
                            # Match OpenCV's morphology default: outside pixels do not
                            # shrink a white object during erosion.
                            if 0 <= yy < height and 0 <= xx < width and src[yy, xx] == 0:
                                keep = 0
                                break
                        if keep == 0:
                            break
                    dst[y, x] = keep
        return np.asarray(dst, dtype=np.uint8)

    def dilate_once(src: np.ndarray) -> np.ndarray:
        dst = pymp.shared.array(mask.shape, dtype=np.uint8)
        with pymp.Parallel() as parallel:
            for y in parallel.range(height):
                for x in range(width):
                    value = 0
                    for ky in range(-radius, radius + 1):
                        for kx in range(-radius, radius + 1):
                            yy = y + ky
                            xx = x + kx
                            if 0 <= yy < height and 0 <= xx < width and src[yy, xx] > 0:
                                value = 255
                                break
                        if value == 255:
                            break
                    dst[y, x] = value
        return np.asarray(dst, dtype=np.uint8)

    opened = dilate_once(erode_once(mask))
    return erode_once(dilate_once(opened))


def opencv_open_close(mask: np.ndarray, kernel_size: int) -> np.ndarray:
    kernel = np.ones((kernel_size, kernel_size), dtype=np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
    return mask


def cpp_open_close(mask: np.ndarray, kernel_size: int) -> np.ndarray:
    import morphology_ext

    return morphology_ext.open_close_mask(mask, kernel_size)


def load_backend(name: str) -> MorphologyFn:
    if name == "python":
        return pure_python_open_close
    if name == "pymp":
        try:
            import pymp  # noqa: F401

            return pymp_open_close
        except Exception:
            return pure_python_open_close
    if name == "cpp":
        try:
            import morphology_ext  # noqa: F401

            return cpp_open_close
        except Exception:
            return opencv_open_close
    return opencv_open_close


@dataclass
class HSVColorTracker:
    config: TrackerConfig

    def __post_init__(self) -> None:
        self.backend = load_backend(self.config.backend)
        self.last_center: tuple[float, float] | None = None
        self.last_bbox: tuple[int, int, int, int] | None = None
        self.last_bbox_float: tuple[float, float, float, float] | None = None
        self.last_area: float = 0.0
        self.last_confidence: float = 0.0
        self.last_mask: np.ndarray | None = None
        self.missed_frames = 0
        if self.config.color_name in self.config.color_presets:
            self.set_color(self.config.color_name)

    @property
    def color_name(self) -> str:
        return self.config.color_name

    @property
    def hsv_ranges(self) -> list[dict[str, list[int]]]:
        return copy_hsv_ranges(self.config.hsv_ranges)

    def available_colors(self) -> list[str]:
        return sorted(self.config.color_presets.keys())

    def set_color(self, color_name: str) -> None:
        if color_name not in self.config.color_presets:
            raise ValueError(f"unknown color preset: {color_name}")
        self.config.color_name = color_name
        self.config.hsv_ranges = copy_hsv_ranges(self.config.color_presets[color_name])
        self.reset_tracking_memory()

    def set_hsv_ranges(self, ranges: list[dict[str, list[int]]], color_name: str = "custom") -> None:
        if not ranges:
            raise ValueError("at least one HSV range is required")
        normalized = copy_hsv_ranges(ranges)
        self.config.color_name = color_name
        self.config.hsv_ranges = normalized
        self.config.color_presets[color_name] = copy_hsv_ranges(normalized)
        self.reset_tracking_memory()

    def reset_tracking_memory(self) -> None:
        self.last_center = None
        self.last_bbox = None
        self.last_bbox_float = None
        self.last_area = 0.0
        self.last_confidence = 0.0
        self.last_mask = None
        self.missed_frames = 0

    @staticmethod
    def _ranges_from_hsv_pixels(
        pixels: np.ndarray,
        hue_margin: int,
        sv_margin: int,
        min_s: int = 25,
        min_v: int = 25,
    ) -> list[dict[str, list[int]]]:
        saturated = pixels[(pixels[:, 1] >= min_s) & (pixels[:, 2] >= min_v)]
        if saturated.size == 0:
            saturated = pixels
        median = np.median(saturated, axis=0).astype(int)
        h = int(median[0])
        s_low = int(max(min_s, np.percentile(saturated[:, 1], 5) - sv_margin))
        v_low = int(max(min_v, np.percentile(saturated[:, 2], 5) - sv_margin * 1.3))
        s_high = int(min(255, np.percentile(saturated[:, 1], 98) + sv_margin))
        v_high = int(min(255, np.percentile(saturated[:, 2], 98) + sv_margin))
        hue_margin = max(1, int(hue_margin))

        if h - hue_margin < 0:
            return [
                {"lower": [0, s_low, v_low], "upper": [h + hue_margin, s_high, v_high]},
                {"lower": [180 + h - hue_margin, s_low, v_low], "upper": [180, s_high, v_high]},
            ]
        if h + hue_margin > 180:
            return [
                {"lower": [h - hue_margin, s_low, v_low], "upper": [180, s_high, v_high]},
                {"lower": [0, s_low, v_low], "upper": [h + hue_margin - 180, s_high, v_high]},
            ]
        return [{"lower": [h - hue_margin, s_low, v_low], "upper": [h + hue_margin, s_high, v_high]}]

    @staticmethod
    def _lerp_ranges(
        old_ranges: list[dict[str, list[int]]],
        new_ranges: list[dict[str, list[int]]],
        alpha: float,
    ) -> list[dict[str, list[int]]]:
        if len(old_ranges) != len(new_ranges):
            return copy_hsv_ranges(new_ranges)
        alpha = max(0.0, min(1.0, float(alpha)))
        blended: list[dict[str, list[int]]] = []
        for old, new in zip(old_ranges, new_ranges):
            lower = [int(round(old["lower"][idx] * (1.0 - alpha) + new["lower"][idx] * alpha)) for idx in range(3)]
            upper = [int(round(old["upper"][idx] * (1.0 - alpha) + new["upper"][idx] * alpha)) for idx in range(3)]
            blended.append(normalize_hsv_range({"lower": lower, "upper": upper}))
        return blended

    def calibrate_from_frame(
        self,
        frame: np.ndarray,
        roi_size: int = 80,
        hue_margin: int | None = None,
        sv_margin: int | None = None,
    ) -> list[dict[str, list[int]]]:
        if hue_margin is None:
            hue_margin = self.config.adaptive_hue_margin
        if sv_margin is None:
            sv_margin = self.config.adaptive_sv_margin
        height, width = frame.shape[:2]
        half = max(8, roi_size // 2)
        cx = width // 2
        cy = height // 2
        x1 = max(0, cx - half)
        x2 = min(width, cx + half)
        y1 = max(0, cy - half)
        y2 = min(height, cy + half)
        roi = frame[y1:y2, x1:x2]
        if roi.size == 0:
            raise ValueError("calibration ROI is empty")

        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        pixels = hsv.reshape(-1, 3)
        ranges = self._ranges_from_hsv_pixels(pixels, hue_margin, sv_margin, min_s=25, min_v=25)
        self.set_hsv_ranges(ranges, color_name="custom")
        return self.hsv_ranges

    def _adapt_hsv_from_detection(self, frame: np.ndarray, bbox: tuple[int, int, int, int], confidence: float, area: float) -> None:
        if not self.config.adaptive_hsv_enabled:
            return
        if confidence < 0.65 or area < max(float(self.config.min_area) * 1.4, 80.0):
            return
        x, y, w, h = bbox
        if w <= 4 or h <= 4:
            return
        inset_x = max(1, int(w * 0.18))
        inset_y = max(1, int(h * 0.18))
        x1 = max(0, x + inset_x)
        y1 = max(0, y + inset_y)
        x2 = min(frame.shape[1], x + w - inset_x)
        y2 = min(frame.shape[0], y + h - inset_y)
        roi = frame[y1:y2, x1:x2]
        if roi.size == 0:
            return
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        pixels = hsv.reshape(-1, 3)
        new_ranges = self._ranges_from_hsv_pixels(
            pixels,
            hue_margin=self.config.adaptive_hue_margin,
            sv_margin=self.config.adaptive_sv_margin,
            min_s=20,
            min_v=20,
        )
        self.config.hsv_ranges = self._lerp_ranges(
            self.config.hsv_ranges,
            new_ranges,
            self.config.adaptive_hsv_alpha,
        )

    def _build_mask(self, hsv_frame: np.ndarray, bgr_frame: np.ndarray | None = None) -> np.ndarray:
        mask = np.zeros(hsv_frame.shape[:2], dtype=np.uint8)
        for hsv_range in self.config.hsv_ranges:
            lower = np.array(hsv_range["lower"], dtype=np.uint8)
            upper = np.array(hsv_range["upper"], dtype=np.uint8)
            mask = cv2.bitwise_or(mask, cv2.inRange(hsv_frame, lower, upper))
        if bgr_frame is not None and self._should_add_red_dominance_mask():
            b, g, r = cv2.split(bgr_frame)
            strongest_other = cv2.max(b, g)
            bright_enough = r >= int(self.config.red_min_channel)
            red_dominant = (r.astype(np.int16) - strongest_other.astype(np.int16)) >= int(self.config.red_margin)
            dominance_mask = np.where(bright_enough & red_dominant, 255, 0).astype(np.uint8)
            mask = cv2.bitwise_or(mask, dominance_mask)
        return mask

    def _should_add_red_dominance_mask(self) -> bool:
        if not self.config.red_dominance_enabled:
            return False
        if self.config.color_name.lower() == "red":
            return True
        return any(item["lower"][0] <= 10 or item["upper"][0] >= 165 for item in self.config.hsv_ranges)

    def _candidate_score(
        self,
        area: float,
        center_x: float,
        center_y: float,
        fill_ratio: float,
        aspect: float,
        jump_limit: float,
    ) -> float:
        score = area * max(0.05, min(1.0, fill_ratio))
        square_score = max(0.25, 1.0 - abs(aspect - 1.0))
        score *= square_score * square_score
        if self.last_center is None:
            return score
        dx = center_x - self.last_center[0]
        dy = center_y - self.last_center[1]
        distance = (dx * dx + dy * dy) ** 0.5
        inertia = max(float(self.config.selection_inertia_px), 1.0)
        if self.last_bbox is not None:
            last_area = max(float(self.last_bbox[2] * self.last_bbox[3]), 1.0)
            area_ratio = area / last_area
            if distance > jump_limit and area_ratio < float(self.config.jump_reject_area_ratio):
                return 0.0
        return score / (1.0 + (distance / inertia) ** 2)

    def _smooth_detection(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        raw_center_x: float,
        raw_center_y: float,
        area: float,
        confidence: float,
        mask: np.ndarray,
    ) -> TargetDetection:
        center_x = raw_center_x
        center_y = raw_center_y
        bbox_x = float(x)
        bbox_y = float(y)
        bbox_w = float(w)
        bbox_h = float(h)
        if self.last_center is not None:
            alpha = max(0.0, min(0.95, float(self.config.detection_smoothing)))
            center_x = self.last_center[0] * alpha + center_x * (1.0 - alpha)
            center_y = self.last_center[1] * alpha + center_y * (1.0 - alpha)
            if self.last_bbox_float is not None:
                bbox_x = self.last_bbox_float[0] * alpha + bbox_x * (1.0 - alpha)
                bbox_y = self.last_bbox_float[1] * alpha + bbox_y * (1.0 - alpha)
                bbox_w = self.last_bbox_float[2] * alpha + bbox_w * (1.0 - alpha)
                bbox_h = self.last_bbox_float[3] * alpha + bbox_h * (1.0 - alpha)
        smoothed_bbox = (
            int(round(bbox_x)),
            int(round(bbox_y)),
            int(round(bbox_w)),
            int(round(bbox_h)),
        )
        self.last_center = (center_x, center_y)
        self.last_bbox_float = (bbox_x, bbox_y, bbox_w, bbox_h)
        self.last_bbox = smoothed_bbox
        self.last_area = area
        self.last_confidence = confidence
        self.last_mask = mask
        self.missed_frames = 0
        return TargetDetection(
            found=True,
            center_x=int(round(center_x)),
            center_y=int(round(center_y)),
            bbox=smoothed_bbox,
            area=area,
            confidence=confidence,
            mask=mask,
        )

    def _held_detection(self, mask: np.ndarray) -> TargetDetection | None:
        if self.last_center is None or self.last_bbox is None:
            return None
        if self.missed_frames >= max(0, int(self.config.lost_hold_frames)):
            return None
        self.missed_frames += 1
        decay = max(0.05, min(1.0, float(self.config.held_confidence_decay)))
        confidence = max(0.05, self.last_confidence * (decay ** self.missed_frames))
        return TargetDetection(
            found=True,
            center_x=int(round(self.last_center[0])),
            center_y=int(round(self.last_center[1])),
            bbox=self.last_bbox,
            area=self.last_area,
            confidence=confidence,
            mask=mask,
        )

    def detect(self, frame: np.ndarray) -> TargetDetection:
        blur_size = self.config.blur_kernel
        if blur_size % 2 == 0:
            blur_size += 1
        blurred = cv2.GaussianBlur(frame, (blur_size, blur_size), 0)
        hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
        mask = self._build_mask(hsv, blurred)
        mask = cv2.medianBlur(mask, 3)
        mask = self.backend(mask, self.config.morph_kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        frame_area = frame.shape[0] * frame.shape[1]
        candidates: list[Candidate] = []
        jump_limit = self._effective_jump_limit(frame.shape[1], frame.shape[0])

        for contour in contours:
            area = cv2.contourArea(contour)
            if area < self.config.min_area:
                continue
            if area > frame_area * self.config.max_area_ratio:
                continue
            x, y, w, h = cv2.boundingRect(contour)
            (_, _), (rect_w, rect_h), _ = cv2.minAreaRect(contour)
            short_side = max(min(rect_w, rect_h), 1.0)
            long_side = max(rect_w, rect_h)
            aspect = long_side / short_side
            if aspect < float(self.config.target_aspect_min) or aspect > float(self.config.target_aspect_max):
                continue
            fill_ratio = area / max(float(rect_w * rect_h), 1.0)
            if fill_ratio < float(self.config.min_rect_fill_ratio):
                continue
            moments = cv2.moments(contour)
            if moments["m00"]:
                center_x = moments["m10"] / moments["m00"]
                center_y = moments["m01"] / moments["m00"]
            else:
                center_x = x + w / 2.0
                center_y = y + h / 2.0
            score = self._candidate_score(area, center_x, center_y, fill_ratio, aspect, jump_limit)
            if score <= 0.0:
                continue
            candidates.append(Candidate(x, y, w, h, center_x, center_y, area, fill_ratio, aspect, score))

        best = self._select_best_candidate(candidates, jump_limit)

        if best is None:
            held = self._held_detection(mask)
            if held is not None:
                return held
            self.reset_tracking_memory()
            return TargetDetection(found=False, mask=mask)

        confidence = min(1.0, best.area / max(float(self.config.min_area) * 5.0, 1.0))
        detection = self._smooth_detection(best.x, best.y, best.w, best.h, best.center_x, best.center_y, best.area, confidence, mask)
        if detection.bbox is not None:
            self._adapt_hsv_from_detection(frame, detection.bbox, detection.confidence, detection.area)
        return detection

    def _effective_jump_limit(self, frame_width: int, frame_height: int) -> float:
        configured = max(float(self.config.max_jump_px), 1.0)
        scaled = max(24.0, min(frame_width, frame_height) * 0.30)
        return min(configured, scaled)

    def _select_best_candidate(self, candidates: list[Candidate], jump_limit: float) -> Candidate | None:
        if not candidates:
            return None
        if self.last_center is not None:
            nearby = [
                candidate
                for candidate in candidates
                if ((candidate.center_x - self.last_center[0]) ** 2 + (candidate.center_y - self.last_center[1]) ** 2) ** 0.5 <= jump_limit
            ]
            if nearby:
                return max(nearby, key=lambda candidate: candidate.score)
        return max(candidates, key=lambda candidate: candidate.score)
