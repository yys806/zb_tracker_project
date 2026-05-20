from __future__ import annotations

from dataclasses import dataclass
import time

from .config import ControlConfig, HardwareConfig


class PanTiltHardware:
    def set_pan(self, angle: float) -> None:
        raise NotImplementedError

    def set_tilt(self, angle: float) -> None:
        raise NotImplementedError

    def move_to(self, pan: float, tilt: float) -> None:
        self.set_pan(pan)
        self.set_tilt(tilt)

    def clamp_pan(self, angle: float) -> float:
        raise NotImplementedError

    def clamp_tilt(self, angle: float) -> float:
        raise NotImplementedError

    def shutdown(self) -> None:
        pass


@dataclass
class MockPanTiltHardware(PanTiltHardware):
    control: ControlConfig
    pan: float = 90.0
    tilt: float = 90.0

    def __post_init__(self) -> None:
        self.pan = self.control.pan_center
        self.tilt = self.control.tilt_center

    def clamp_pan(self, angle: float) -> float:
        return max(self.control.pan_min, min(self.control.pan_max, angle))

    def clamp_tilt(self, angle: float) -> float:
        return max(self.control.tilt_min, min(self.control.tilt_max, angle))

    def set_pan(self, angle: float) -> None:
        self.pan = self.clamp_pan(angle)

    def set_tilt(self, angle: float) -> None:
        self.tilt = self.clamp_tilt(angle)


class AdafruitPanTiltHardware(PanTiltHardware):
    def __init__(self, hardware_cfg: HardwareConfig, control_cfg: ControlConfig) -> None:
        import board
        import busio
        from adafruit_motor import servo
        from adafruit_pca9685 import PCA9685

        self.control = control_cfg
        self.pan = control_cfg.pan_center
        self.tilt = control_cfg.tilt_center
        i2c = busio.I2C(board.SCL, board.SDA)
        self.pca = PCA9685(i2c, address=hardware_cfg.i2c_address)
        self.pca.frequency = hardware_cfg.frequency_hz
        self.pan_servo = servo.Servo(self.pca.channels[hardware_cfg.pan_channel])
        self.tilt_servo = servo.Servo(self.pca.channels[hardware_cfg.tilt_channel])
        self.pan_servo.set_pulse_width_range(hardware_cfg.min_pulse, hardware_cfg.max_pulse)
        self.tilt_servo.set_pulse_width_range(hardware_cfg.min_pulse, hardware_cfg.max_pulse)
        self.move_to(self.pan, self.tilt)

    def clamp_pan(self, angle: float) -> float:
        return max(self.control.pan_min, min(self.control.pan_max, angle))

    def clamp_tilt(self, angle: float) -> float:
        return max(self.control.tilt_min, min(self.control.tilt_max, angle))

    def set_pan(self, angle: float) -> None:
        self.pan = self.clamp_pan(angle)
        self.pan_servo.angle = self.pan

    def set_tilt(self, angle: float) -> None:
        self.tilt = self.clamp_tilt(angle)
        self.tilt_servo.angle = self.tilt

    def shutdown(self) -> None:
        self.pca.deinit()


class SmbusPanTiltHardware(PanTiltHardware):
    MODE1 = 0x00
    MODE2 = 0x01
    PRESCALE = 0xFE
    LED0_ON_L = 0x06

    def __init__(self, hardware_cfg: HardwareConfig, control_cfg: ControlConfig, bus_id: int = 1) -> None:
        from smbus2 import SMBus

        self.hardware = hardware_cfg
        self.control = control_cfg
        self.bus = SMBus(bus_id)
        self.pan = control_cfg.pan_center
        self.tilt = control_cfg.tilt_center
        self._init_pca9685(hardware_cfg.frequency_hz)
        self.move_to(self.pan, self.tilt)

    def _write_reg(self, reg: int, value: int) -> None:
        self.bus.write_byte_data(self.hardware.i2c_address, reg, value)

    def _init_pca9685(self, frequency_hz: int) -> None:
        self._write_reg(self.MODE1, 0x00)
        self._write_reg(self.MODE2, 0x04)
        prescale = int(25000000.0 / 4096.0 / float(frequency_hz) - 1.0 + 0.5)
        oldmode = self.bus.read_byte_data(self.hardware.i2c_address, self.MODE1)
        self._write_reg(self.MODE1, (oldmode & 0x7F) | 0x10)
        self._write_reg(self.PRESCALE, prescale)
        self._write_reg(self.MODE1, oldmode)
        time.sleep(0.005)
        self._write_reg(self.MODE1, oldmode | 0xA1)

    def _angle_to_count(self, angle: float) -> int:
        pulse_us = self.hardware.min_pulse + (self.hardware.max_pulse - self.hardware.min_pulse) * angle / 180.0
        period_us = 1_000_000.0 / float(self.hardware.frequency_hz)
        return int(4096.0 * pulse_us / period_us)

    def _set_pwm(self, channel: int, on: int, off: int) -> None:
        base = self.LED0_ON_L + 4 * channel
        addr = self.hardware.i2c_address
        self.bus.write_byte_data(addr, base, on & 0xFF)
        self.bus.write_byte_data(addr, base + 1, on >> 8)
        self.bus.write_byte_data(addr, base + 2, off & 0xFF)
        self.bus.write_byte_data(addr, base + 3, off >> 8)

    def clamp_pan(self, angle: float) -> float:
        return max(self.control.pan_min, min(self.control.pan_max, angle))

    def clamp_tilt(self, angle: float) -> float:
        return max(self.control.tilt_min, min(self.control.tilt_max, angle))

    def set_pan(self, angle: float) -> None:
        self.pan = self.clamp_pan(angle)
        self._set_pwm(self.hardware.pan_channel, 0, self._angle_to_count(self.pan))

    def set_tilt(self, angle: float) -> None:
        self.tilt = self.clamp_tilt(angle)
        self._set_pwm(self.hardware.tilt_channel, 0, self._angle_to_count(self.tilt))

    def shutdown(self) -> None:
        self.bus.close()


def create_hardware(hardware_cfg: HardwareConfig, control_cfg: ControlConfig, force_mock: bool = False) -> PanTiltHardware:
    if force_mock or hardware_cfg.force_mock:
        return MockPanTiltHardware(control_cfg)
    smbus_error: Exception | None = None
    try:
        return SmbusPanTiltHardware(hardware_cfg, control_cfg, bus_id=1)
    except Exception as exc:
        smbus_error = exc

    try:
        return AdafruitPanTiltHardware(hardware_cfg, control_cfg)
    except Exception as adafruit_error:
        raise RuntimeError(
            "real hardware initialization failed. "
            "Use --simulate for mock mode, or check I2C/PCA9685 permissions and wiring. "
            f"smbus error: {smbus_error}; adafruit error: {adafruit_error}"
        ) from adafruit_error
