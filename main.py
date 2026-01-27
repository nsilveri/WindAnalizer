from machine import I2C
import rp2
from lib.SDL_INA3221_MP import SDL_INA3221
from lib.picozero import pico_led
from lib.elapsed_time import elapsed_time
from lib.dht import DHT11
from lib.wifi_connection import scan, connect
from lib.web_server import start_server
import threading
import time

# Database TinyDB
#db = TinyDB('data.json')

# I2C Config
i2c = I2C(1, scl=1, sda=0)

# Sensore DHT11
DIHT_PIN = 14
dht_sensor = DHT11(DIHT_PIN)

# INA3221 Initialization
INA3221_ADDR = 0x42
ina = None

try:
    ina = SDL_INA3221(i2c, addr=INA3221_ADDR)
except Exception as e:
    print("INA3221 Initialization Error:", e)

def read_ina3221(CHANNEL=1):
    try:
        if ina is None:
            return
        
        if CHANNEL not in [1, 2, 3]:
            raise ValueError("Invalid channel. Must be 1, 2, or 3.")
        
        v_channel = ina.get_bus_voltage(CHANNEL)
        i_channel = ina.get_current(CHANNEL)

        print("CH{}: V={:.2f}V I={:.2f}A".format(CHANNEL, v_channel, i_channel))
        return v_channel, i_channel

    except Exception as e:
        print("INA3221 Read Error:", e)

# WiFi Connection
rp2.country('IT')

print(scan())
print(connect('SPHGROUPWIFI-2g', 'SPHGROUP2024'))
#start_server()

# Avvio thread server web
server_thread = threading.Thread(target=start_server, args=(dht_sensor, wind_speed))
server_thread.start()

try:
    while True:
        if ina is not None:
            read_ina3221()
        time.sleep(1)
        
except KeyboardInterrupt:
    print("Interrupted by user.")