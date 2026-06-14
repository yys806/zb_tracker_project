from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


HsvRange = dict[str, list[int]]
HsvPresetMap = dict[str, list[HsvRange]]


def default_color_presets() -> HsvPresetMap:
    return {
        "red": [
            {"lower": [0, 70, 45], "upper": [15, 255, 255]},
            {"lower": [165, 70, 45], "upper": [180, 255, 255]},
        ],
        "blue": [
            {"lower": [95, 90, 60], "upper": [130, 255, 255]},
        ],
        "green": [
            {"lower": [40, 70, 60], "upper": [85, 255, 255]},
        ],
        "yellow": [
            {"lower": [20, 90, 80], "upper": [38, 255, 255]},
        ],
        "custom": [
            {"lower": [0, 80, 60], "upper": [180, 255, 255]},
        ],
    }


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
    hsv_ranges: list[HsvRange]
    color_name: str = "red"
    color_presets: HsvPresetMap = field(default_factory=default_color_presets)
    red_dominance_enabled: bool = True
    red_min_channel: int = 70
    red_margin: int = 28
    detection_smoothing: float = 0.35
    selection_inertia_px: float = 80.0
    min_rect_fill_ratio: float = 0.58
    max_jump_px: float = 100.0
    jump_reject_area_ratio: float = 2.2
    target_aspect_min: float = 0.65
    target_aspect_max: float = 1.45
    lost_hold_frames: int = 3
    held_confidence_decay: float = 0.55
    adaptive_hsv_enabled: bool = True
    adaptive_hsv_alpha: float = 0.06
    adaptive_hue_margin: int = 16
    adaptive_sv_margin: int = 90


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
    servo_min_delta_deg: float = 0.35
    pan_max_step_deg: float | None = None
    tilt_max_step_deg: float | None = None
    pan_smoothing: float | None = None
    tilt_smoothing: float | None = None
    pan_deadzone_px: float | None = None
    tilt_deadzone_px: float | None = None
    pan_min_delta_deg: float | None = None
    tilt_min_delta_deg: float | None = None
    tilt_hold_enter_px: float | None = None
    tilt_hold_release_px: float | None = None
    tilt_settle_frames: int = 0
    tilt_settle_release_px: float | None = None
    pan_direction: float = -1.0
    tilt_direction: float = -1.0


@dataclass(slots=True)
class StateMachineConfig:
    lock_frames: int
    lost_frames: int
    search_after_seconds: float
    search_step_deg: float
    search_pan_span: float
    enable_search: bool = False


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
class GestureConfig:
    enabled: bool = False
    backend: str = "auto"
    mediapipe_model_complexity: int = 0
    mediapipe_min_detection_confidence: float = 0.55
    mediapipe_min_tracking_confidence: float = 0.55
    mediapipe_process_every_n: int = 2
    min_area: int = 1800
    min_area_ratio: float = 0.01
    max_area_ratio: float = 0.55
    blur_kernel: int = 5
    morph_kernel: int = 7
    min_defect_depth: float = 18.0
    max_defect_angle_deg: float = 95.0
    stable_frames: int = 2
    skin_ycrcb_lower: list[int] = field(default_factory=lambda: [0, 133, 77])
    skin_ycrcb_upper: list[int] = field(default_factory=lambda: [255, 173, 127])
    skin_hsv_lower: list[int] = field(default_factory=lambda: [0, 25, 35])
    skin_hsv_upper: list[int] = field(default_factory=lambda: [25, 220, 255])


@dataclass(slots=True)
class HardwareConfig:
    force_mock: bool
    i2c_address: int
    pan_channel: int
    tilt_channel: int
    frequency_hz: int
    min_pulse: int
    max_pulse: int
    center_on_start: bool = False
    release_on_start: bool = True
    release_on_shutdown: bool = False
    reset_step_deg: float = 2.0
    reset_step_delay_s: float = 0.035


@dataclass(slots=True)
class AppConfig:
    camera: CameraConfig
    tracker: TrackerConfig
    control: ControlConfig
    state_machine: StateMachineConfig
    logging: LoggingConfig
    ui: UIConfig
    hardware: HardwareConfig
    gesture: GestureConfig = field(default_factory=GestureConfig)


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
        gesture=GestureConfig(**raw.get("gesture", {})),
    )


def save_config(config: AppConfig, path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(asdict(config), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
