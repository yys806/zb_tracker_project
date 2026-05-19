from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import cv2
import numpy as np

from .config import TrackerConfig
from .types import TargetDetection


MorphologyFn = Callable[[np.ndarray, int], np.ndarray]


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
                        if yy < 0 or yy >= height or xx < 0 or xx >= width or src[yy, xx] == 0:
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
