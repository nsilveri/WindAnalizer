import machine
import time

class DHT11:
    def __init__(self, pin):
        self.pin = machine.Pin(pin, machine.Pin.IN, machine.Pin.PULL_UP)
        self.temperature = 0
        self.humidity = 0

    def measure(self):
        # Send start signal
        self.pin.init(machine.Pin.OUT)
        self.pin.value(0)
        time.sleep_ms(18)
        self.pin.value(1)
        self.pin.init(machine.Pin.IN, machine.Pin.PULL_UP)

        # Wait for response
        pulses = []
        while self.pin.value() == 1:
            pass
        while self.pin.value() == 0:
            pass
        while self.pin.value() == 1:
            pass

        # Read data
        for i in range(40):
            while self.pin.value() == 0:
                pass
            start = time.ticks_us()
            while self.pin.value() == 1:
                pass
            end = time.ticks_us()
            pulses.append(time.ticks_diff(end, start))

        # Convert pulses to bits
        data = []
        for pulse in pulses:
            if pulse > 50:
                data.append(1)
            else:
                data.append(0)

        # Convert to bytes
        if len(data) == 40:
            humidity = 0
            temperature = 0
            for i in range(8):
                humidity += data[i] << (7 - i)
                temperature += data[16 + i] << (7 - i)

            checksum = 0
            for i in range(32):
                checksum += data[i]
            checksum &= 0xFF

            if checksum == (data[32] + (data[33] << 1) + (data[34] << 2) + (data[35] << 3) + (data[36] << 4) + (data[37] << 5) + (data[38] << 6) + (data[39] << 7)):
                self.humidity = humidity
                self.temperature = temperature
                return True
        return False