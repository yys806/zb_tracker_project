import smbus2
import sys

def scan_i2c(bus_number=1):
    print(f"Scanning I2C bus /dev/i2c-{bus_number}...")
    try:
        bus = smbus2.SMBus(bus_number)
    except Exception as e:
        print(f"Error: Could not open I2C bus {bus_number}. {e}")
        return False

    found_devices = []
    for address in range(0x03, 0x78):
        try:
            bus.write_quick(address)
            found_devices.append(hex(address))
        except OSError:
            pass

    found_pca9685 = "0x40" in found_devices
    if found_devices:
        print(f"Done! Found devices at: {', '.join(found_devices)}")
        if found_pca9685:
            print("Found PCA9685 at 0x40")
        if '0x70' in found_devices:
            print("Found PCA9685 All-Call at 0x70")
    else:
        print("No I2C devices found. Check wiring and ensure I2C is enabled.")
    bus.close()
    if not found_pca9685:
        print("PCA9685 0x40 was not found on this I2C bus.")
    return found_pca9685

if __name__ == "__main__":
    bus_num = 1
    if len(sys.argv) > 1:
        bus_num = int(sys.argv[1])
    raise SystemExit(0 if scan_i2c(bus_num) else 1)
