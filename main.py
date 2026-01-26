from lib.SDL_INA3221_MP import SDL_INA3221
from machine import I2C
import time

INA3221_ADDR = 0x42

# I2C Config
i2c = I2C(1, scl=1, sda=0)

ina = None

try:
    ina = SDL_INA3221(i2c, addr=INA3221_ADDR)
except Exception as e:
    print("INA3221 Initialization Error:", e)

def read_ina3221():
    try:
        v1 = ina.get_bus_voltage(1)
        i1 = ina.get_current(1)
        v2 = ina.get_bus_voltage(2)
        i2 = ina.get_current(2)
        v3 = ina.get_bus_voltage(3)
        i3 = ina.get_current(3)
        print("CH1: V={:.2f}V I={:.2f}A | CH2: V={:.2f}V I={:.2f}A | CH3: V={:.2f}V I={:.2f}A".format(
            v1, i1, v2, i2, v3, i3
        ))
    except Exception as e:
        print("INA3221 Read Error:", e)

try:
    while True:
        if ina is not None:
            read_ina3221()
        time.sleep(1)
except KeyboardInterrupt:
    print("Interrupted by user.")