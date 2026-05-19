from __future__ import annotations

import cv2

from .config import CameraConfig


class OpenCVCamera:
    def __init__(self, config: CameraConfig) -> None:
        self.config = config
        self.capture = cv2.VideoCapture(config.device_index)
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, config.width)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, config.height)
        self.capture.set(cv2.CAP_PROP_FPS, config.fps)

    def read(self):
        ok, frame = self.capture.read()
        if not ok:
            return False, None
        if self.config.mirror:
            frame = cv2.flip(frame, 1)
        return True, frame

    def release(self) -> None:
        self.capture.release()

