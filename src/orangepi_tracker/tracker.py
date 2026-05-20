from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import cv2
import numpy as np

from .config import TrackerConfig
from .types import TargetDetection


MorphologyFn = Callable[[np.ndarray, int], np.ndarray]
HSV_LIMITS = ((0, 180), (0, 255), (0, 255))


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

    def set_hsv_ranges(self, ranges: list[dict[str, list[int]]], color_name: str = "custom") -> None:
        if not ranges:
            raise ValueError("at least one HSV range is required")
        normalized = copy_hsv_ranges(ranges)
        self.config.color_name = color_name
        self.config.hsv_ranges = normalized
        self.config.color_presets[color_name] = copy_hsv_ranges(normalized)

    def calibrate_from_frame(
        self,
        frame: np.ndarray,
        roi_size: int = 80,
        hue_margin: int = 10,
        sv_margin: int = 45,
    ) -> list[dict[str, list[int]]]:
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
        median = np.median(hsv.reshape(-1, 3), axis=0).astype(int)
        h, s, v = (int(median[0]), int(median[1]), int(median[2]))
        s_low = max(40, s - sv_margin)
        v_low = max(40, v - sv_margin)
        s_high = min(255, s + sv_margin)
        v_high = min(255, v + sv_margin)

        if h - hue_margin < 0:
            ranges = [
                {"lower": [0, s_low, v_low], "upper": [h + hue_margin, s_high, v_high]},
                {"lower": [180 + h - hue_margin, s_low, v_low], "upper": [180, s_high, v_high]},
            ]
        elif h + hue_margin > 180:
            ranges = [
                {"lower": [h - hue_margin, s_low, v_low], "upper": [180, s_high, v_high]},
                {"lower": [0, s_low, v_low], "upper": [h + hue_margin - 180, s_high, v_high]},
            ]
        else:
            ranges = [{"lower": [h - hue_margin, s_low, v_low], "upper": [h + hue_margin, s_high, v_high]}]

        self.set_hsv_ranges(ranges, color_name="custom")
        return self.hsv_ranges

    def _build_mask(self, hsv_frame: np.ndarray) -> np.ndarray:
        mask = np.zeros(hsv_frame.shape[:2], dtype=np.uint8)
        for hsv_range in self.config.hsv_ranges:
            lower = np.array(hsv_range["lower"], dtype=np.uint8)
            upper = np.array(hsv_range["upper"], dtype=np.uint8)
            mask = cv2.bitwise_or(mask, cv2.inRange(hsv_frame, lower, upper))
        return mask

    def detect(self, frame: np.ndarray) -> TargetDetection:
        blur_size = self.config.blur_kernel
        if blur_size % 2 == 0:
            blur_size += 1
        blurred = cv2.GaussianBlur(frame, (blur_size, blur_size), 0)
        hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
        mask = self._build_mask(hsv)
        mask = self.backend(mask, self.config.morph_kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        frame_area = frame.shape[0] * frame.shape[1]
        best = None
        best_area = 0.0

        for contour in contours:
            area = cv2.contourArea(contour)
            if area < self.config.min_area:
                continue
            if area > frame_area * self.config.max_area_ratio:
                continue
            x, y, w, h = cv2.boundingRect(contour)
            aspect = w / max(h, 1)
            if aspect < 0.3 or aspect > 3.5:
                continue
            if area > best_area:
                best_area = area
                best = (x, y, w, h)

        if best is None:
            return TargetDetection(found=False, mask=mask)

        x, y, w, h = best
        center_x = x + w // 2
        center_y = y + h // 2
        confidence = min(1.0, best_area / max(float(self.config.min_area) * 5.0, 1.0))
        return TargetDetection(
            found=True,
            center_x=center_x,
            center_y=center_y,
            bbox=(x, y, w, h),
            area=best_area,
            confidence=confidence,
            mask=mask,
        )
