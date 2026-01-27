from lib.SDL_INA3221_MP import SDL_INA3221
from machine import I2C
import time

INA3221_ADDR = 0x42

# I2C Config
i2c = I2C(0, scl=1, sda=0)

# Wind scale factor [V, mt/s]
VOLT = 0
SPEED = 1
min_scale = [ 0.12, 2.5]
max_scale = [ 0.62, 10.3]

# Initial I2C scanner
def scan_i2c():
    try:
        devices = i2c.scan()
        if devices:
            print("I2C devices found:", ", ".join("0x{:02X}".format(d) for d in devices))
        else:
            print("No I2C devices found.")
    except Exception as e:
        print("I2C scan error:", e)

# Run initial scan
scan_i2c()

# INA3221 Initialization
ina = None
try:
    ina = SDL_INA3221(i2c, addr=INA3221_ADDR)
except Exception as e:
    print("INA3221 Initialization Error:", e)

# Read INA3221 Data
def read_ina3221():
    try:
        #v_1 = ina.get_bus_voltage(1)
        v_bus_1 = ina.get_bus_voltage(1)
        #i1 = ina.get_current(1)

        return v_bus_1
    
    except Exception as e:
        print("INA3221 Read Error:", e)

# Convert voltage to wind speed
def voltageToWindSpeed(voltage, min_scale, max_scale):
    OUT_OF_SCALE = False

    if voltage < min_scale[VOLT] or voltage > max_scale[VOLT]:
        OUT_OF_SCALE = True
    else:
        OUT_OF_SCALE = False

    scale = (max_scale[SPEED] - min_scale[SPEED]) / (max_scale[VOLT] - min_scale[VOLT])
    wind_speed = min_scale[SPEED] + scale * (voltage - min_scale[VOLT])

    return wind_speed, OUT_OF_SCALE

# Print wind speed information
def printWindInfo(windSpeed, outOfScale):
    if outOfScale:
        print("Wind Speed: {:.2f} mt/s, WARNING: Wind Speed Out of Scale".format(windSpeed))
    else:
        print("Wind Speed: {:.2f} mt/s".format(windSpeed))

try:
    while True:
        if ina is not None:
            voltFromAnemometer = read_ina3221()
            windSpeed, outOfScale = voltageToWindSpeed(voltFromAnemometer, min_scale, max_scale)
            printWindInfo(windSpeed, outOfScale)

        time.sleep(0.2)
except KeyboardInterrupt:
    print("Interrupted by user.")