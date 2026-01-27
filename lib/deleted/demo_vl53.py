from machine import Pin, I2C
from time import ticks_ms

from vl53l5cx_mp.mp import VL53L5CXMP
from vl53l5cx_mp import RESOLUTION_4X4, RESOLUTION_8X8, RANGING_MODE_CONTINUOUS
from vl53l5cx_mp import DATA_DISTANCE_MM, DATA_TARGET_STATUS
from vl53l5cx_mp import STATUS_VALID, STATUS_VALID_LARGE_PULSE

from lib.i2c_multiplexer import TcaI2CMultiplexer

# pins and multiplexer channel (set VL53_CHANNEL to the channel used)
sda_pin, scl_pin, lpn_pin = (0, 1, 14)
VL53_CHANNEL = 0  # change to actual channel 0-7

# I2C bus used for sensor + multiplexer
i2c = I2C(0, scl=Pin(scl_pin), sda=Pin(sda_pin))
i2c_mux = TcaI2CMultiplexer(i2c)

def main():
    tof = VL53L5CXMP(i2c, lpn=Pin(lpn_pin, Pin.OUT, value=1))
    tof.reset()
    tof.init()

    tof.resolution = RESOLUTION_8X8
    grid = 8

    tof.ranging_freq = 15
    tof.ranging_mode = RANGING_MODE_CONTINUOUS
    tof.integration_time_ms = 15

    tof.start_ranging({DATA_DISTANCE_MM, DATA_TARGET_STATUS})

    prev = ticks_ms()
    while True:
        if tof.check_data_ready():
            now = ticks_ms()
            delta = now - prev
            prev = now

            results = tof.get_ranging_data()
            distances = results.distance_mm
            target = results.target_status

            print("distance matrix:")
            for i in range(len(distances)):
                print(distances[i], end=" ")
                if (i + 1) % grid == 0:
                    print()
            print("----")

def i2c_scan():
    print("Scansione I2C in corso...")
    devices = i2c.scan()
    if devices:
        print("Dispositivi I2C trovati:", [hex(device) for device in devices])
    else:
        print("Nessun dispositivo I2C trovato.")


i2c_scan()
main()