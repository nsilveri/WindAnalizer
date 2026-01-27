from lib.ina_sensor_reader import init_ina, read_bus_voltage
from lib.wind_output import voltage_to_wind_speed, min_scale, max_scale, print_wind_info
import time

INA3221_ADDR = 0x42

# Init INA3221 sensor
ina = init_ina(addr=INA3221_ADDR)

try:
    while True:
        if ina is not None:
            voltFromAnemometer = read_bus_voltage(ina)
            windSpeed, outOfScale = voltage_to_wind_speed(voltFromAnemometer, min_scale, max_scale)
            print_wind_info(windSpeed, outOfScale)

        time.sleep(0.2)
        
except KeyboardInterrupt:
    print("Interrupted by user.")