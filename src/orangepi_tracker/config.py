from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class CameraConfig:
    device_index: int
    width: int
    height: int
    fps: int
    mirror: bool


@dataclass(slots=True)
class TrackerConfig:
    backend: str
    min_area: int
    max_area_ratio: float
    blur_kernel: int
    morph_kernel: int
    hsv_ranges: list[dict[str, list[int]]]


@dataclass(slots=True)
class ControlConfig:
    pan_center: float
    tilt_center: float
    pan_min: float
    pan_max: float
    tilt_min: float
    tilt_max: float
    deadzone_px: float
    pan_kp: float
    pan_ki: float
    pan_kd: float
    tilt_kp: float
    tilt_ki: float
    tilt_kd: float
    max_step_deg: float
    smoothing: float


@dataclass(slots=True)
class StateMachineConfig:
    lock_frames: int
    lost_frames: int
    search_after_seconds: float
    search_step_deg: float
    search_pan_span: float


@dataclass(slots=True)
class LoggingConfig:
    enabled: bool
    log_dir: str


@dataclass(slots=True)
class UIConfig:
    show_window: bool
    window_name: str
    draw_mask_preview: bool


@dataclass(slots=True)
class HardwareConfig:
    force_mock: bool
    i2c_address: int
    pan_channel: int
    tilt_channel: int
    frequency_hz: int
    min_pulse: int
    max_pulse: int


@dataclass(slots=True)
class AppConfig:
    camera: CameraConfig
    tracker: TrackerConfig
    control: ControlConfig
    state_machine: StateMachineConfig
    logging: LoggingConfig
    ui: UIConfig
    hardware: HardwareConfig


def load_config(path: str | Path) -> AppConfig:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return AppConfig(
        camera=CameraConfig(**raw["camera"]),
        tracker=TrackerConfig(**raw["tracker"]),
        control=ControlConfig(**raw["control"]),
        state_machine=StateMachineConfig(**raw["state_machine"]),
        logging=LoggingConfig(**raw["logging"]),
        ui=UIConfig(**raw["ui"]),
        hardware=HardwareConfig(**raw["hardware"]),
    )

