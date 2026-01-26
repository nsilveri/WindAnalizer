"""Minimal `I2CDevice` shim for MicroPython.

This implements a very small subset of the API from
`adafruit_bus_device.i2c_device.I2CDevice` that is commonly used by
CircuitPython drivers: context manager, `readinto`, `writeto`, and
`writeto_then_readinto`.

It uses the underlying `machine.I2C` methods (`writeto`,
`readfrom_into`) which are available on most MicroPython ports.
"""

class I2CDevice:
    def __init__(self, i2c, address, probe=False):
        self.i2c = i2c
        self.address = address

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        # nothing to cleanup
        return False

    def readinto(self, buf, start=0, end=None):
        # readinto ignores start/end; drivers typically provide full buffers
        try:
            self.i2c.readfrom_into(self.address, buf)
        except AttributeError:
            # Some ports use readfrom_into with different name
            self.i2c.readfrom_into(self.address, buf)

    def writeto(self, buf, stop=True):
        # stop parameter ignored; underlying API usually doesn't expose it
        self.i2c.writeto(self.address, buf)

    # CircuitPython drivers use `write` and `write_then_readinto` on the
    # I2CDevice. Provide these aliases with a compatible signature.
    def write(self, buf):
        self.i2c.writeto(self.address, buf)

    def write_then_readinto(self, out_buf, in_buf, out_start=0, out_end=None, in_start=0, in_end=None):
        # Slice outgoing buffer according to optional start/end parameters
        if out_end is None:
            out_segment = out_buf[out_start:]
        else:
            out_segment = out_buf[out_start:out_end]

        # Perform write then read into; for simplicity we ignore in_start/in_end on the read
        self.i2c.writeto(self.address, out_segment)
        # Read into the provided buffer (full length or up to in_end)
        if in_end is None:
            self.i2c.readfrom_into(self.address, in_buf)
        else:
            # read into a temporary buffer then copy slice
            temp = bytearray(in_end - in_start)
            self.i2c.readfrom_into(self.address, temp)
            in_buf[in_start:in_end] = temp

__all__ = ["I2CDevice"]
