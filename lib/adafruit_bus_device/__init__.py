"""Minimal adafruit_bus_device package shim for MicroPython.

This package provides a very small compatibility layer implementing
`I2CDevice` used by CircuitPython drivers so they can run on
MicroPython devices where the Adafruit helper package is not
available. It implements only the methods required by the driver in
this repo (basic read/write/context manager helpers).
"""

__all__ = ["i2c_device"]
