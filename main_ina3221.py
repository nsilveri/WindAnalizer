from lib.ina_sensor_reader import init_ina, read_bus_voltage
from lib.wind_output import voltage_to_wind_speed, min_scale, max_scale, print_wind_info
from lib.wind_db import init_db, insert_record
from lib.sdcard_writer import SDCardFS
from lib.is_pico_w import is_pico_w
from lib.ds1302 import DS1302 as RTC_DS1302
#from lib.wifi_connection import connect, scan
from lib.internal_memory_info import print_memory_info
#from lib.get_ntp_time import getTimeNTP
import time

INA3221_ADDR = 0x42
TIMEZONE = 'Europe/Rome'

IS_PICO_W = is_pico_w()

# Try to mount SD and initialize DB on SD; fall back to internal storage
SD_MOUNT_POINT = '/sd'
sd_fs = SDCardFS(mount_point=SD_MOUNT_POINT, format_sd=False)
use_sd = False
try:
    sd_fs.mount()
    use_sd = True
except Exception as e:
    print('SD mount failed, using internal storage:', e)

# Init DB (pass SD path when available)
db_path = SD_MOUNT_POINT + '/data/wind' if use_sd else None
db = init_db(db_path=db_path) if db_path else init_db()

# Memory info
print_memory_info()

# Init INA3221 sensor (log an error record if not found)
ina = None
try:
    ina = init_ina(addr=INA3221_ADDR)
except Exception as e:
    print("Failed to initialize INA3221 sensor:", e)
    try:
        # store an error record immediately
        insert_record(db, time.time(), None, True, message='ina_init_error')
    except Exception as ie:
        print('Failed to record INA init error:', ie)
    ina = None

# Connect to WiFi
if IS_PICO_W:
    from lib.wifi_connection import connect, scan

    print(scan())
    connection = connect('your_ssid', 'your_password')
    print(connection)

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
            insert_record(db, time.time(), None, True, message='ina_missing')
            break

        time.sleep(1)

except KeyboardInterrupt:
    print("Interrupted by user.")
    try:
        sd_fs.umount()
    except Exception:
        pass