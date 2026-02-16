# SPDX-FileCopyrightText: 2017 Scott Shawcroft, written for Adafruit Industries
# SPDX-FileCopyrightText: Copyright (c) 2025 senseBox for senseBox
#
# SPDX-License-Identifier: Unlicense

def main():
    """Example main loop kept for reference but not auto-run on import.
    Use `create_tof()` to get a sensor instance and then call
    `read_ranging_once(tof)` or your own loop from `main.py`.
    """
    raise RuntimeError("Do not call main() directly; import and use create_tof()")


# Try to support both CircuitPython (busio/board/digitalio) and
# MicroPython (user-provided I2C/pin). If CircuitPython modules are
# available we auto-create I2C and LPN pin; otherwise the caller must
# pass compatible objects.
try:
    import board
    import busio
    from digitalio import DigitalInOut, Direction
    _CIRCUITPY = True
except Exception:
    from machine import I2C, Pin
    _CIRCUITPY = False

from vl53lxcx import (
    DATA_DISTANCE_MM,
    DATA_TARGET_STATUS,
    RESOLUTION_8X8,
    STATUS_VALID,
    VL53L8CX,
)

i2c_m = I2C(1, scl=11, sda=10)


class _PinWrapper:
    """Wrap a machine.Pin to look like DigitalInOut for the driver."""

    def __init__(self, pin):
        self._pin = pin
        # emulate direction attribute
        self.direction = None

    @property
    def value(self):
        try:
            return self._pin.value()
        except Exception:
            # some machine.Pin implementations use .value without call
            return self._pin.value

    @value.setter
    def value(self, v):
        try:
            self._pin.value(1 if v else 0)
        except Exception:
            try:
                self._pin.value = 1 if v else 0
            except Exception:
                pass


class _NoopLpn:
    """A no-op LPN object for boards where the LPN/XSHUT pin is not used.

    The driver may call `.value = False`/`True` to reset the sensor; this
    object accepts those operations but does nothing, leaving the sensor
    permanently enabled (useful when only one sensor is on the bus).
    """

    def __init__(self, initial=True):
        self._v = True if initial else False

    @property
    def value(self):
        return self._v

    @value.setter
    def value(self, v):
        # ignore writes
        self._v = bool(v)


def create_tof(i2c=None, lpn_pin=None, lpn_obj=None):
    """Create and return a configured VL53L8CX instance.

    Parameters:
    - i2c: an I2C object (optional). If omitted and running CircuitPython,
      an I2C will be created from `board` and `busio`.
    - lpn_pin: a pin identifier to use if `lpn_obj` is not provided.
      On CircuitPython this should be a `board` pin (e.g. `board.D3`).
    - lpn_obj: an object with a boolean `value` property; if provided it is
      used directly as LPN control.

    Returns: VL53L8CX instance
    """
    if i2c is None:
        if _CIRCUITPY:
            i2c = busio.I2C(board.SCL, board.SDA, frequency=1_000_000)
        else:
            raise ValueError("i2c object required when not running CircuitPython")

    if lpn_obj is None:
        if _CIRCUITPY:
            if lpn_pin is None:
                lpn_pin = board.D3
            lpn = DigitalInOut(lpn_pin)
            lpn.direction = Direction.OUTPUT
            lpn.value = True
        else:
            # For MicroPython, allow omitting lpn_pin: use a no-op LPN
            # object so the sensor remains enabled if you don't have a
            # hardware reset pin wired. If a pin is provided, wrap it.
            if lpn_pin is None:
                lpn = _NoopLpn(initial=True)
            else:
                try:
                    from machine import Pin

                    if isinstance(lpn_pin, Pin):
                        p = lpn_pin
                    else:
                        p = Pin(lpn_pin, Pin.OUT)
                    lpn = _PinWrapper(p)
                    lpn.value = True
                except Exception as e:
                    raise ValueError("Could not create LPN pin: " + str(e))
    else:
        lpn = lpn_obj

    tof = VL53L8CX(i2c, lpn=lpn)
    return tof


def read_ranging_once(tof):
    """Start ranging once and return (distance_list, status_list).

    This does not loop forever; caller controls timing.
    """
    tof.reset()

    if not tof.is_alive():
        raise ValueError("VL53L8CX not detected")

    tof.init()
    tof.resolution = RESOLUTION_8X8
    tof.ranging_freq = 2
    tof.start_ranging({DATA_DISTANCE_MM, DATA_TARGET_STATUS})

    # Wait for a measurement to be ready. Caller can replace with better
    # scheduling if desired.
    import time

    timeout = 2.0
    t0 = time.time()
    while True:
        if tof.check_data_ready():
            results = tof.get_ranging_data()
            return results.distance_mm, results.target_status
        if time.time() - t0 > timeout:
            raise TimeoutError("Ranging data not ready")
        time.sleep(0.01)


def format_grid(distance, status, grid_width=8):
    """Return a string with a formatted grid of distances for printing."""
    out_lines = []
    row = []
    for i, d in enumerate(distance):
        if status[i] == STATUS_VALID:
            row.append(f"{d:4}")
        else:
            row.append("xxxx")
        if (i & (grid_width - 1)) == (grid_width - 1):
            out_lines.append(" ".join(row))
            row = []
    if row:
        out_lines.append(" ".join(row))
    return "\n".join(out_lines)


def run_test_loop(i2c=None, lpn_pin=None, interval_s=0.5, iterations=None):
    """Run a simple continuous test loop printing ranges.

    - If `i2c` is None and running CircuitPython, the I2C bus will be
      auto-created. On MicroPython provide a `machine.I2C` instance.
    - `lpn_pin` can be a board pin (CircuitPython) or a machine.Pin or
      pin id (MicroPython). If omitted on CircuitPython a default pin is
      used.
    - `interval_s` is the delay between reads.
    - `iterations` limits the number of loops (None = infinite).
    """
    # Create TOF device
    tof = create_tof(i2c=i2c_m, lpn_pin=lpn_pin)

    count = 0
    try:
        import time
        while iterations is None or count < iterations:
            try:
                distance, status = read_ranging_once(tof)
                try:
                    print("\n" + format_grid(distance, status))
                except Exception:
                    print("Distances:", distance)
            except Exception as e:
                print("Read error:", e)
            count += 1
            time.sleep(interval_s)
    finally:
        # best-effort cleanup: if the TOF object exposes a deinit/stop, call it
        try:
            if hasattr(tof, "stop_ranging"):
                tof.stop_ranging()
        except Exception:
            pass


if __name__ == "__main__":
    # When run directly, perform a short test (10 iterations) to avoid
    # accidentally locking the REPL forever.
    try:
        run_test_loop(interval_s=0.5, iterations=10)
    except Exception as e:
        print("Test run failed:", e)
