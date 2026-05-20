import time
import smbus2

# PCA9685 Registers
MODE1 = 0x00
PRESCALE = 0xFE
LED0_ON_L = 0x06

class PCA9685Driver:
    def __init__(self, bus_number=1, address=0x40):
        self.address = address
        self.bus = smbus2.SMBus(bus_number)
        self.boot_device()

    def write_reg(self, reg, value):
        self.bus.write_byte_data(self.address, reg, value)

    def read_reg(self, reg):
        return self.bus.read_byte_data(self.address, reg)

    def boot_device(self):
        self.write_reg(MODE1, 0x00) # Reset
        self.set_pwm_freq(50)       # Standard 50Hz for servos

    def set_pwm_freq(self, freq_hz):
        prescale_val = int(25000000.0 / (4096.0 * freq_hz) - 1.0)
        old_mode = self.read_reg(MODE1)
        new_mode = (old_mode & 0x7F) | 0x10  # Enter Sleep mode
        self.write_reg(MODE1, new_mode)
        self.write_reg(PRESCALE, prescale_val)
        self.write_reg(MODE1, old_mode)
        time.sleep(0.005)
        self.write_reg(MODE1, old_mode | 0x80) # Restart

    def set_pwm(self, channel, on, off):
        base_reg = LED0_ON_L + 4 * channel
        self.write_reg(base_reg, on & 0xFF)
        self.write_reg(base_reg + 1, on >> 8)
        self.write_reg(base_reg + 2, off & 0xFF)
        self.write_reg(base_reg + 3, off >> 8)

    def set_angle(self, channel, angle):
        # Map 0-180 degrees to pulse width
        # 0.5ms (approx 102/4096) to 2.5ms (approx 512/4096)
        off_val = int(102 + (angle / 180.0) * (512 - 102))
        self.set_pwm(channel, 0, off_val)

    def close(self):
        self.bus.close()

def run_test():
    try:
        # Using I2C bus 1 and PCA9685 at 0x40
        servo = PCA9685Driver(bus_number=1, address=0x40)
        print("--- PCA9685 Low-Level Test Started (using smbus2) ---")
        print("Moving Channel 0 and 1 through safe angles once.")

        for angle in [90, 75, 105, 90]:
            print(f"Current Target: {angle} degrees")
            servo.set_angle(0, angle)
            servo.set_angle(1, angle)
            time.sleep(1)

        print("Low-level servo test finished.")
        servo.close()
                
    except KeyboardInterrupt:
        print("\nTest finished.")
    except Exception as e:
        print(f"\nError occurred: {e}")
        raise SystemExit(1)

if __name__ == "__main__":
    run_test()
