from machine import Pin, I2C

class SDL_INA3221:
    # Constants
    INA3221_ADDRESS = 0x40
    
    # Registers
    REG_CONFIG = 0x00
    REG_SHUNTVOLTAGE_1 = 0x01
    REG_BUSVOLTAGE_1 = 0x02
    
    # Configuration bits
    CONFIG_ENABLE_CHAN1 = 0x4000
    CONFIG_ENABLE_CHAN2 = 0x2000
    CONFIG_ENABLE_CHAN3 = 0x1000
    CONFIG_AVG1 = 0x0400
    CONFIG_VBUS_CT2 = 0x0100
    CONFIG_VSH_CT2 = 0x0020
    CONFIG_MODE_2 = 0x0004
    CONFIG_MODE_1 = 0x0002
    CONFIG_MODE_0 = 0x0001
    
    def __init__(self, i2c, addr=INA3221_ADDRESS, shunt_resistor=0.1):
        self._i2c = i2c
        self._addr = addr
        self._shunt_resistor = shunt_resistor
        
        # Initial configuration
        config = (self.CONFIG_ENABLE_CHAN1 |
                 self.CONFIG_ENABLE_CHAN2 |
                 self.CONFIG_ENABLE_CHAN3 |
                 self.CONFIG_AVG1 |
                 self.CONFIG_VBUS_CT2 |
                 self.CONFIG_VSH_CT2 |
                 self.CONFIG_MODE_2 |
                 self.CONFIG_MODE_1 |
                 self.CONFIG_MODE_0)
        
        self._write_register(self.REG_CONFIG, config)
    
    def _write_register(self, reg, value):
        """Write 16-bit value to register."""
        buffer = bytearray(3)
        buffer[0] = reg
        buffer[1] = (value >> 8) & 0xFF  # MSB
        buffer[2] = value & 0xFF         # LSB
        self._i2c.writeto(self._addr, buffer)
    
    def _read_register(self, reg):
        """Read 16-bit value from register."""
        self._i2c.writeto(self._addr, bytes([reg]))
        data = self._i2c.readfrom(self._addr, 2)
        value = (data[0] << 8) | data[1]
        # Handle signed values
        if value > 32767:
            value -= 65536
        return value
    
    def get_bus_voltage(self, channel):
        """Get bus voltage in volts."""
        raw = self._read_register(self.REG_BUSVOLTAGE_1 + (channel - 1) * 2)
        return raw * 0.001
    
    def get_shunt_voltage(self, channel):
        """Get shunt voltage in millivolts."""
        raw = self._read_register(self.REG_SHUNTVOLTAGE_1 + (channel - 1) * 2)
        return raw * 0.005
    
    def get_current(self, channel):
        """Get current in milliamps."""
        shunt_voltage = self.get_shunt_voltage(channel)
        return shunt_voltage / self._shunt_resistor

    def get_power(self, channel):
        """Get power in watts."""
        voltage = self.get_bus_voltage(channel)
        current = self.get_current(channel) / 1000  # Convert mA to A
        return voltage * current