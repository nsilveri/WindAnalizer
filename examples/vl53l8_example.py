"""Example runner for VL53L8CX using `vl53lxcx_simpletest` helpers.

This example works on both CircuitPython and MicroPython.

Usage:
- CircuitPython: copy this file to the board and run it (it will auto-create
  I2C and LPN pin using `board` and `busio`).
- MicroPython: edit the `MICROPY_I2C_ID`, `MICROPY_SCL_PIN`, `MICROPY_SDA_PIN`,
  and `MICROPY_LPN_PIN` constants to match your board, then upload and run.

Adjust delays and pins as needed for your hardware.
"""

try:
    from vl53lxcx_simpletest import create_tof, read_ranging_once, format_grid
except Exception as e:
    print("Failed to import vl53lxcx_simpletest helpers:", e)
    raise

try:
    import board  # type: ignore
    CIRCUITPY = True
except Exception:
    CIRCUITPY = False


def main():
    if CIRCUITPY:
        # CircuitPython: helper will create busio I2C and DigitalInOut for LPN
        tof = create_tof()
    else:
        # MicroPython: adapt these to your board
        MICROPY_I2C_ID = 0
        MICROPY_SCL_PIN = 22
        MICROPY_SDA_PIN = 21
        MICROPY_LPN_PIN = 2

        from machine import I2C, Pin

        i2c = I2C(MICROPY_I2C_ID, scl=Pin(MICROPY_SCL_PIN), sda=Pin(MICROPY_SDA_PIN))
        lpn = Pin(MICROPY_LPN_PIN, Pin.OUT)
        tof = create_tof(i2c=i2c, lpn_pin=lpn)

    try:
        while True:
            distance, status = read_ranging_once(tof)
            print(format_grid(distance, status))
            # sleep between readings
            try:
                import time

                time.sleep(0.5)
            except Exception:
                pass
    except KeyboardInterrupt:
        print("Stopped by user")


if __name__ == "__main__":
    main()
