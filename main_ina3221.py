from lib.ina_sensor_reader import init_ina, read_bus_voltage
from lib.wind_output import voltage_to_wind_speed, min_scale, max_scale, print_wind_info
from lib.wind_db import init_db, insert_record
from lib.sdcard_writer import SDCardFS
from lib.is_pico_w import is_pico_w
import wifi_credentials
from lib.ds1302.ds1302 import DS1302 as RTC_DS1302
from machine import Pin
#from lib.wifi_connection import connect, scan
from lib.internal_memory_info import print_memory_info
from lib.get_ntp_time import getTimeNTP
import time

INA3221_ADDR = 0x42
TIMEZONE = 'Europe/Rome'

# Behaviour when INA3221 is missing
INA_RETRY_INTERVAL_SEC = 5
INA_MISSING_LOG_INTERVAL_SEC = 10

IS_PICO_W = is_pico_w()

# Set up RTC (for timestamping without WiFi)
rtc = RTC_DS1302(clk=Pin(28), dio=Pin(27), cs=Pin(26))
rtc_time = None
try:
    if hasattr(rtc, 'start'):
        try:
            rtc.start()
        except Exception:
            pass

    if hasattr(rtc, 'date_time'):
        rtc_time = rtc.date_time()
    else:
        rtc_time = rtc.datetime()
    print('RTC time:', rtc_time)

except Exception as e:
    print("RTC initialization error:", e)

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
ina = init_ina(addr=INA3221_ADDR)
reported_ina_missing = False
next_ina_retry_ts = 0
next_ina_missing_log_ts = 0

# Connect to WiFi
if IS_PICO_W:
    from lib.wifi_connection import connect, scan

    print(scan())
    connection = connect(wifi_credentials.WIFI_SSID, wifi_credentials.WIFI_PASSWORD)
    print(connection)
    # Optionally, get NTP time (requires WiFi)
    try:
        ntp_time = getTimeNTP(TIMEZONE)
        print('NTP time:', ntp_time)

        # Update RTC with NTP time if available
        if ntp_time and hasattr(rtc, 'date_time'):
            try:
                rtc.date_time(ntp_time)
                print('RTC updated with NTP time.')
            except Exception as e:
                print('Failed to set RTC time:', e)
    except Exception as e:
        print("NTP time error:", e)

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
            # INA missing: keep registering on DB (at a reduced rate) and retry init.
            now = time.time()

            if not reported_ina_missing:
                next_ina_retry_ts = 0
                next_ina_missing_log_ts = 0
                reported_ina_missing = True

            if now >= next_ina_missing_log_ts:
                try:
                    insert_record(db, now, None, True, message='ina_missing')
                except Exception:
                    pass
                next_ina_missing_log_ts = now + INA_MISSING_LOG_INTERVAL_SEC

            if now >= next_ina_retry_ts:
                ina = init_ina(addr=INA3221_ADDR)
                next_ina_retry_ts = now + INA_RETRY_INTERVAL_SEC

            time.sleep(1)
            continue

        time.sleep(1)

except KeyboardInterrupt:
    print("Interrupted by user.")
    try:
        sd_fs.umount()
    except Exception:
        pass