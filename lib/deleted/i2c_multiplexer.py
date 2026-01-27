class TcaI2CMultiplexer:
    """
    Library for controlling a TCA9548A I2C multiplexer using MicroPython's I2C API.
    """

    def __init__(self, i2c, address=0x70):
        """
        Initialize the multiplexer.
        :param i2c: A machine.I2C instance.
        :param address: I2C address of the multiplexer (default 0x70).
        """
        self.i2c = i2c
        self.address = address

    def disable_all(self):
        """
        Disable all channels.
        """
        self.i2c.writeto(self.address, b'\x00')

    def enable_channel(self, channel):
        """
        Enable a single channel (0-7).
        """
        if not 0 <= channel <= 7:
            raise ValueError("Channel must be 0-7")
        self.i2c.writeto(self.address, bytes([1 << channel]))

    def enable_channels(self, channels):
        """
        Enable multiple channels at once.
        :param channels: Iterable of channel numbers (0-7).
        """
        value = 0
        for ch in channels:
            if not 0 <= ch <= 7:
                raise ValueError("Channel must be 0-7")
            value |= (1 << ch)
        self.i2c.writeto(self.address, bytes([value]))

    def scan(self):
        """
        Scan the I2C bus and return a list of detected device addresses.
        """
        for ch in range(8):
            self.enable_channel(ch)
            devices = self.i2c.scan()
            print(f"Channel {ch}: Found devices {['0x{:02x}'.format(d) for d in devices]}")
            
        
        return devices

    def get_enabled_channels(self):
        """
        Read and return a list of enabled channels.
        """
        status = self.i2c.readfrom(self.address, 1)[0]
        return [ch for ch in range(8) if status & (1 << ch)]

    def enable_all(self):
        """
        Enable all 8 channels.
        """
        self.i2c.writeto(self.address, b'\xff')