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
from lib.get_ntp_time import getTimeNTP, ntp_utc_to_europe_rome
import time


def _set_machine_rtc_from_ds(dt):
    """Set MicroPython internal RTC from a DS1302-style datetime list.

    DS1302 date_time() format: [Y, M, D, weekday, hh, mm, ss]
    machine.RTC().datetime() format: (Y, M, D, weekday, hh, mm, ss, subseconds)
    """
    try:
        if not dt or len(dt) < 7:
            return False
        y, m, d, wd, hh, mm, ss = int(dt[0]), int(dt[1]), int(dt[2]), int(dt[3]), int(dt[4]), int(dt[5]), int(dt[6])
        from machine import RTC
        RTC().datetime((y, m, d, wd, hh, mm, ss, 0))
        return True
    except Exception:
        return False

try:
    from secrets import TELEGRAM_BOT_TOKEN, TELEGRAM_ALLOWED_CHAT_IDS
except Exception:
    TELEGRAM_BOT_TOKEN = None
    TELEGRAM_ALLOWED_CHAT_IDS = None

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

    # Keep MicroPython internal RTC in sync so time.time()/localtime() are correct.
    if rtc_time and hasattr(rtc, 'date_time'):
        _set_machine_rtc_from_ds(rtc_time)

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

# Shared state for Telegram /status
wind_state = {'latest_record': None, 'rtc': rtc, 'timezone': TIMEZONE}
telegram_bot = None

# Connect to WiFi
if IS_PICO_W:
    from lib.wifi_connection import connect, scan

    print(scan())
    connection = connect(wifi_credentials.WIFI_SSID, wifi_credentials.WIFI_PASSWORD)
    print(connection)
    # Optionally, get NTP time (requires WiFi)
    try:
        ntp_time_utc = getTimeNTP(TIMEZONE)
        print('NTP time (UTC):', ntp_time_utc)

        # Convert UTC -> local (Europe/Rome) for setting RTCs.
        ntp_time_local = ntp_utc_to_europe_rome(ntp_time_utc) if TIMEZONE == 'Europe/Rome' else ntp_time_utc
        print('NTP time (local):', ntp_time_local)

        # Expose NTP info to Telegram bot (/rtc)
        try:
            wind_state['ntp_time_utc'] = ntp_time_utc
            wind_state['ntp_time_local'] = ntp_time_local
        except Exception:
            pass

        # Update RTC with NTP time if available
        if ntp_time_local and hasattr(rtc, 'date_time'):
            try:
                # NTP local tuple: (Y,M,D,hh,mm,ss,weekday,yearday)
                y, m, d, hh, mm, ss, wd = int(ntp_time_local[0]), int(ntp_time_local[1]), int(ntp_time_local[2]), int(ntp_time_local[3]), int(ntp_time_local[4]), int(ntp_time_local[5]), int(ntp_time_local[6])
                ds_dt = [y, m, d, wd, hh, mm, ss]

                try:
                    wind_state['ntp_ds_dt_local'] = ds_dt
                except Exception:
                    pass

                rtc.date_time(ds_dt)
                _set_machine_rtc_from_ds(ds_dt)
                print('RTC updated with NTP time.')
            except Exception as e:
                print('Failed to set RTC time:', e)
    except Exception as e:
        print("NTP time error:", e)

    # Telegram bot (optional)
    if TELEGRAM_BOT_TOKEN:
        try:
            from lib.wind_telegram_bot import WindTelegramBot
            telegram_bot = WindTelegramBot(
                token=TELEGRAM_BOT_TOKEN,
                db_table=db,
                state=wind_state,
                allowed_chat_ids=TELEGRAM_ALLOWED_CHAT_IDS,
                debug=False,
            )
            print('Telegram bot enabled')
        except Exception as e:
            print('Telegram bot init error:', e)

try:
    while True:
        if telegram_bot is not None:
            telegram_bot.poll()

        if ina is not None:
            voltFromAnemometer = read_bus_voltage(ina)
            windSpeed, outOfScale = voltage_to_wind_speed(voltFromAnemometer, min_scale, max_scale)
            print_wind_info(windSpeed, outOfScale)

            # Store reading
            try:
                insert_record(db, time.time(), windSpeed, outOfScale)
            except Exception:
                pass

            # Update latest record snapshot for Telegram
            wind_state['latest_record'] = {
                'timestamp': str(time.time()),
                'windspeed': '' if windSpeed is None else str(windSpeed),
                'outofscale': str(bool(outOfScale)),
            }
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

                # Update latest record snapshot for Telegram
                wind_state['latest_record'] = {
                    'timestamp': str(now),
                    'windspeed': '',
                    'outofscale': 'True',
                    'message': 'ina_missing',
                }

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