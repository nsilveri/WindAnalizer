# The MIT License (MIT)
#
# Copyright (c) 2017 Dean Miller for Adafruit Industries
# Copyright (c) 2020 Christian Becker
#
# Modified 2025 for Rshunt = 0.002 Ω (20A max) by <tuo_nome>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
"""
`ina226`
====================================================

Driver MicroPython per il sensore **INA226**.

Configurazione:
    - Rshunt = 0.002 Ω (2 mΩ)
    - Corrente massima ≈ 20 A
    - Corrente restituita in **milliAmpere**
    - Potenza in **Watt**

"""

from micropython import const

__version__ = "0.0.2"
__repo__ = "https://github.com/elschopi/TI_INA226_micropython.git"

# -------------------------------------------------------------------------
# Registri e costanti
# -------------------------------------------------------------------------
_READ = const(0x01)

_REG_CONFIG      = const(0x00)
_CONFIG_RESET    = const(0x8000)
_CONFIG_CONST_BITS = const(0x4000)

_CONFIG_AVGMODE_512SAMPLES = const(0x0c00)

_CONFIG_VBUSCT_588us  = const(0x00c0)
_CONFIG_VSHUNTCT_588us = const(0x0018)

_CONFIG_MODE_SANDBVOLT_CONTINUOUS = const(0x0007)

_REG_SHUNTVOLTAGE = const(0x01)
_REG_BUSVOLTAGE   = const(0x02)
_REG_POWER        = const(0x03)
_REG_CURRENT      = const(0x04)
_REG_CALIBRATION  = const(0x05)


def _to_signed(num):
    if num > 0x7FFF:
        num -= 0x10000
    return num


class INA226:
    """Driver per INA226 (corrente in mA, tensione in Volt, potenza in Watt)."""

    def __init__(self, i2c_device, addr=0x40):
        self.i2c_device = i2c_device
        self.i2c_addr = addr
        self.buf = bytearray(2)
        self._current_lsb = 0
        self._power_lsb = 0
        self._cal_value = 0
        self.set_calibration()

    # ---------------------------------------------------------------------
    # Accesso ai registri
    # ---------------------------------------------------------------------
    def _write_register(self, reg, value):
        self.buf[0] = (value >> 8) & 0xFF
        self.buf[1] = value & 0xFF
        self.i2c_device.writeto_mem(self.i2c_addr, reg, self.buf)

    def _read_register(self, reg):
        self.i2c_device.readfrom_mem_into(self.i2c_addr, reg & 0xFF, self.buf)
        return (self.buf[0] << 8) | self.buf[1]

    # ---------------------------------------------------------------------
    # Misure
    # ---------------------------------------------------------------------
    @property
    def shunt_voltage(self):
        """Tensione sullo shunt in Volt."""
        value = _to_signed(self._read_register(_REG_SHUNTVOLTAGE))
        # LSB = 10 µV
        return value * 0.00001

    @property
    def bus_voltage(self):
        """Tensione di bus in Volt."""
        raw_voltage = self._read_register(_REG_BUSVOLTAGE)
        # LSB = 1.25 mV
        return raw_voltage * 0.00125

    @property
    def current(self):
        """Corrente attraverso lo shunt in **milliAmpere**."""
        self._write_register(_REG_CALIBRATION, self._cal_value)
        raw_current = _to_signed(self._read_register(_REG_CURRENT))
        return raw_current * self._current_lsb * 1000  # mA

    @property
    def power(self):
        """Potenza calcolata in Watt."""
        raw_power = _to_signed(self._read_register(_REG_POWER))
        return raw_power * self._power_lsb

    # ---------------------------------------------------------------------
    # Calibrazione per Rshunt = 0.002 Ω
    # ---------------------------------------------------------------------
    def set_calibration(self):
        """
        Imposta la calibrazione per:
            - Rshunt = 0.002 Ω
            - Risoluzione corrente = 1 mA/bit
            - Potenza = 25 × corrente
        """
        # 1 mA per bit
        self._current_lsb = 0.001      # Ampere/bit
        self._power_lsb   = 0.025      # Watt/bit
        self._cal_value   = 2560       # 0.00512 / (0.002 * 0.001)
        self._write_register(_REG_CALIBRATION, self._cal_value)

        config = (_CONFIG_CONST_BITS |
                  _CONFIG_AVGMODE_512SAMPLES |
                  _CONFIG_VBUSCT_588us |
                  _CONFIG_VSHUNTCT_588us |
                  _CONFIG_MODE_SANDBVOLT_CONTINUOUS)

        self._write_register(_REG_CONFIG, config)

    def set_calibration_custom(self, cal_value, config):
        """Imposta manualmente calibrazione e configurazione."""
        self._cal_value = cal_value
        self._write_register(_REG_CALIBRATION, self._cal_value)
        self._write_register(_REG_CONFIG, config)
