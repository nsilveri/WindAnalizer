"""
Helper module to mount and perform simple read/write operations
on a microSD card attached to SPI. Importable and safe to import
without side effects.
"""

from machine import SPI, Pin
import lib.sdcard as sdcard
import os


class SDCardFS:
    """Simple filesystem helper around `lib.sdcard.SDCard`.

    Methods:
      - mount()
      - umount()
      - write(path, data, mode='w')
      - append(path, data)
      - read(path)
      - listdir(path=None)
      - exists(path)

    The class does not perform any actions on import; call `mount()` to
    initialize the SPI bus and mount the filesystem.
    """

    def __init__(
        self,
        spi_bus=0,
        cs_pin=17,
        sck_pin=18,
        mosi_pin=19,
        miso_pin=20,
        mount_point="/sd",
        format_sd=False,
        baudrate=1320000,
    ):
        self.spi_bus = spi_bus
        self.cs_pin = cs_pin
        self.sck_pin = sck_pin
        self.mosi_pin = mosi_pin
        self.miso_pin = miso_pin
        self.mount_point = mount_point
        self.format_sd = format_sd
        self.baudrate = baudrate

        self.spi = None
        self.cs = None
        self.sd = None
        self._mounted = False

    def _full_path(self, path: str) -> str:
        if path.startswith("/"):
            return path
        return self.mount_point.rstrip("/") + "/" + path.lstrip("/")

    def _ensure_setup(self):
        if self.spi is None:
            self.spi = SPI(self.spi_bus, sck=Pin(self.sck_pin), mosi=Pin(self.mosi_pin), miso=Pin(self.miso_pin))
            self.cs = Pin(self.cs_pin)

    def mount(self):
        """Initialise SPI, create SDCard instance and mount the filesystem."""
        if self._mounted:
            return
        self._ensure_setup()
        self.sd = sdcard.SDCard(self.spi, self.cs, baudrate=self.baudrate)
        if self.format_sd:
            # may raise OSError if mkfs isn't available
            self.sd.format_sd()
        os.mount(self.sd, self.mount_point)
        self._mounted = True

    def umount(self):
        if not self._mounted:
            return
        try:
            os.umount(self.mount_point)
        finally:
            self._mounted = False

    def write(self, path: str, data: str, mode: str = "w"):
        """Write `data` to `path`. Path may be relative to mount point."""
        if not self._mounted:
            raise OSError("SD card not mounted")
        full = self._full_path(path)
        with open(full, mode) as f:
            f.write(data)

    def append(self, path: str, data: str):
        return self.write(path, data, mode="a")

    def read(self, path: str) -> str:
        if not self._mounted:
            raise OSError("SD card not mounted")
        full = self._full_path(path)
        with open(full, "r") as f:
            return f.read()

    def listdir(self, path: str = None):
        if not self._mounted:
            raise OSError("SD card not mounted")
        if path:
            p = self._full_path(path)
        else:
            p = self.mount_point
        return os.listdir(p)

    def exists(self, path: str) -> bool:
        if not self._mounted:
            raise OSError("SD card not mounted")
        try:
            os.stat(self._full_path(path))
            return True
        except Exception:
            return False


__all__ = ["SDCardFS"]