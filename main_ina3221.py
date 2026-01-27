from lib.ina_sensor_reader import init_ina, read_bus_voltage
from lib.wind_output import voltage_to_wind_speed, min_scale, max_scale, print_wind_info
from lib.wind_db import init_db, insert_record
from lib.wifi_connection import connect, scan
from lib.internal_memory_info import print_memory_info
#from lib.get_ntp_time import getTimeNTP
import time

INA3221_ADDR = 0x42
TIMEZONE = 'Europe/Rome'

# Init INA3221 sensor
ina = None
try:
    ina = init_ina(addr=INA3221_ADDR)
except Exception as e:
    print("Failed to initialize INA3221 sensor:", e)
    ina = None

# Connect to WiFi
print(scan())
connection = connect('your_ssid', 'your_password')
print(connection)

# Init DB
db = init_db()

# Memory info
print_memory_info()

try:
    while True:
        if ina is not None:
            voltFromAnemometer = read_bus_voltage(ina)
            windSpeed, outOfScale = voltage_to_wind_speed(voltFromAnemometer, min_scale, max_scale)
            print_wind_info(windSpeed, outOfScale)

            # Store reading
            try:
                insert_record(db, time.time(), windSpeed, outOfScale)
            except Exception:
                pass
        else:
            # Execute insert one time and stop the loop
            insert_record(db, time.time(), None, True)
            break

        time.sleep(0.2)

except KeyboardInterrupt:
    print("Interrupted by user.")