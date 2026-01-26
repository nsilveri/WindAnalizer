"""I2C target example that keeps running and responds to controller requests.

This script registers an IRQ handler which reacts to READ/WRITE
requests and also includes a fallback polling loop for ports that do
not support hard IRQs. If `machine.I2CTarget` is not available (e.g.
running on a PC), it falls back to the local `i2c_template.I2CTarget`
mock so you can test logic on the host.
"""

from lib.i2c_multiplexer import TcaI2CMultiplexer
from lib.ina226_mp import INA226
from lib.SDL_INA3221_MP import SDL_INA3221
from machine import  I2C, Pin, PWM #I2CTarget
import time
import struct

timer_read = time.ticks_ms()

READ_TEST = False  # Abilita/Disabilita il test di lettura periodica

# Crea la memoria di backing per l'I2C target (1 status byte + 8 payload bytes)
# mem[0] will be status: BUSY or READY. payload is mem[1:9]
mem = bytearray(20)
BUSY = 0x00
READY = 0xAA
msg_recvd = ''

# I2C target setup
SDA_PIN = 0  # Pin SDA
SCL_PIN = 1  # Pin SCL
ADDR = 0x49  # Indirizzo I2C del target

INA1_CHANNEL = 2
INA2_CHANNEL = 7

# INAs Addresses
VL53L8CX_ADDR = 0x29
INA226_1_ADDR = 0x40
INA226_2_ADDR = 0x41
INA3221_ADDR = 0x42

# TCA9548A Address
TCA_ADDR = 0x70

# VL53L5CX multiplexer channel (set to the channel where the sensor is wired)
VL53_CHANNEL = 0  # change this to the actual channel (0-7)

# INAs register configuration
# INA226_1 reg
INA_1_REG = 0x01

# INA226_2 reg
INA_2_REG = 0x02

# INA3221 reg
INA_3_CH1_REG = 0x03
INA_3_CH2_REG = 0x04
INA_3_CH3_REG = 0x05

# Relays reg
RASPBERRY_RELAY = 0x06
IR_LED_CAMERA_RELAY_ON = 0x07
IR_LED_CAMERA_RELAY_OFF = 0x08

# VL53L8CX enable pin
#VL53_LPN_PIN = 14  # change this to the actual pin used
#VL53_LPN = Pin(VL53_LPN_PIN, Pin.OUT, value=1)

# Relays pins PWM Mode

relay1 = Pin(14, Pin.OUT)
#relay2 = Pin(15, Pin.OUT)

relay1_pwm = PWM(relay1)
#relay2_pwm = PWM(relay2)

relay1_pwm.freq(1000)
relay1_pwm.duty_u16(65536)
relay1_pwm.duty_u16(0)


# Crea il target I2C sull'indirizzo 0x49 (73 decimale)
i2c = I2CTarget(addr=ADDR, mem=mem, sda=SDA_PIN, scl=SCL_PIN)
i2c_m = I2C(1, scl=11, sda=10)
i2c_mux = TcaI2CMultiplexer(i2c_m)

ina1 = None
ina2 = None
ina3 = None

# INAs data storage
ina1_data = {'voltage': 0, 'current': 0}
ina2_data = {'voltage': 0, 'current': 0}
ina3_ch1_data = {'voltage': 0, 'current': 0}
ina3_ch2_data = {'voltage': 0, 'current': 0}
ina3_ch3_data = {'voltage': 0, 'current': 0}


def update_all_readings():
    """Periodically read all INA sensors and store rounded values in the
    *_data dictionaries. This keeps readings ready to be returned on request.
    """
    # INA226_1
    try:
        time.sleep_ms(5)
        i2c_mux.enable_channel(INA1_CHANNEL)
        time.sleep_ms(10)
        if ina1 is not None:
            ina1_data['voltage'] = round(ina1.bus_voltage, 2)
            ina1_data['current'] = round(ina1.current, 2)
    except Exception as e:
        print('Errore update INA1:', e)

    # INA226_2
    try:
        i2c_mux.disable_all()
        time.sleep_ms(5)
        i2c_mux.enable_channel(INA2_CHANNEL)
        time.sleep_ms(10)
        if ina2 is not None:
            ina2_data['voltage'] = round(ina2.bus_voltage, 2)
            ina2_data['current'] = round(ina2.current, 2)
    except Exception as e:
        print('Errore update INA2:', e)

    # INA3221 channels (assume INA3221 always on the same mux channel)
    try:
        # ensure INA3221 channel on mux is enabled if needed (here we assume it's on main bus)
        # if ina3 is present, read its 3 channels
        if ina3 is not None:
            # Channel 1
            time.sleep_ms(2)
            ina3_ch1_data['voltage'] = round(ina3.get_bus_voltage(1), 2)
            ina3_ch1_data['current'] = round(ina3.get_current(1), 2)

            # Channel 2
            time.sleep_ms(2)
            ina3_ch2_data['voltage'] = round(ina3.get_bus_voltage(2), 2)
            ina3_ch2_data['current'] = round(ina3.get_current(2), 2)

            # Channel 3
            time.sleep_ms(2)
            ina3_ch3_data['voltage'] = round(ina3.get_bus_voltage(3), 2)
            ina3_ch3_data['current'] = round(ina3.get_current(3), 2)
    except Exception as e:
        print('Errore update INA3221:', e)

# Inizializza il sensore INA226
try:
    i2c_mux.enable_channel(INA1_CHANNEL)
    ina1 = INA226(i2c_m, addr=0x40)
except Exception as e:
    print("Errore di inizializzazione INA226 sul canale", INA1_CHANNEL, ":", e)

# Inizializza il sensore INA226
try:
    i2c_mux.enable_channel(INA2_CHANNEL)
    ina2 = INA226(i2c_m, addr=0x41)
except Exception as e:
    print("Errore di inizializzazione INA226 sul canale", INA2_CHANNEL, ":", e)

# Inizializza il sensore INA3221
try:
    ina3 = SDL_INA3221(i2c_m, addr=0x42)
    
except Exception as e:
    print("Errore di inizializzazione SDL_INA3221 sul canale 3:", e)

# Inizializza il sensore VL53L5CX
try:
    # ensure the multiplexer channel for the VL53 is selected
    i2c_mux.disable_all()
    time.sleep_ms(5)
    i2c_mux.enable_channel(VL53_CHANNEL)
    time.sleep_ms(20)

    vl53 = VL53L5CXMP(i2c_m) # default addr 0x29
    vl53.init()
except Exception as e:
    print("Errore di inizializzazione VL53L5CX:", e)

def i2c_scan():
    print("Scansione I2C in corso...")
    devices = i2c_m.scan()
    if devices:
        print("Dispositivi I2C trovati:", [hex(device) for device in devices])
    else:
        print("Nessun dispositivo I2C trovato.")

try:
    last = bytes(mem)
    i2c_scan()
    enabled_channels = i2c_mux.scan()
    print("Canali abilitati sul multiplexer:", [hex(enabled_channels) for enabled_channels in enabled_channels])
    
    while True:
        # Periodic sensor update every 500 ms
        if time.ticks_diff(time.ticks_ms(), timer_read) >= 500:
            update_all_readings()
            timer_read = time.ticks_ms()
        # Se i dati in mem cambiano, stampali
        if mem != last:
            print("Dati ricevuti:", bytes(mem))
            #msg_recvd = bytes(mem).decode('utf-8').rstrip('\x00')
            print("Messaggio ricevuto:", msg_recvd, "address:", ADDR)
            print("Primo byte ricevuto (comando):", mem[0], "address:", ADDR)

            # Capture command and mark BUSY immediately
            try:
                cmd = mem[0]
                mem[0] = BUSY

                # write payload at offset 1 so master can poll mem[0] for READY
                if cmd == INA_1_REG:
                    voltage = ina1_data['voltage']
                    current = ina1_data['current']
                    print("Return INA1 from storage - Voltage:", voltage, "Current:", current)
                    struct.pack_into('<ff', mem, 1, voltage, current)
                    print("Packed INA1 data into mem:", list(mem))
                elif cmd == INA_2_REG:
                    voltage = ina2_data['voltage']
                    current = ina2_data['current']
                    print("Return INA2 from storage - Voltage:", voltage, "Current:", current)
                    struct.pack_into('<ff', mem, 1, voltage, current)
                    print("Packed INA2 data into mem:", list(mem))
                elif cmd == INA_3_CH1_REG:
                    voltage = ina3_ch1_data['voltage']
                    current = ina3_ch1_data['current']
                    print("Return INA3 CH1 from storage - Voltage:", voltage, "Current:", current)
                    struct.pack_into('<ff', mem, 1, voltage, current)
                    print("Packed INA3 CH1 data into mem:", list(mem))
                elif cmd == INA_3_CH2_REG:
                    voltage = ina3_ch2_data['voltage']
                    current = ina3_ch2_data['current']
                    print("Return INA3 CH2 from storage - Voltage:", voltage, "Current:", current)
                    struct.pack_into('<ff', mem, 1, voltage, current)
                    print("Packed INA3 CH2 data into mem:", list(mem))
                elif cmd == INA_3_CH3_REG:
                    voltage = ina3_ch3_data['voltage']
                    current = ina3_ch3_data['current']
                    print("Return INA3 CH3 from storage - Voltage:", voltage, "Current:", current)
                    struct.pack_into('<ff', mem, 1, voltage, current)
                    print("Packed INA3 CH3 data into mem:", list(mem))
                elif cmd == IR_LED_CAMERA_RELAY_ON:
                    # Toggle IR LED Camera relay state (for example)
                    print("Toggle IR LED Camera Relay ON command received")
                    relay1_pwm.duty_u16(65536)  # Turn ON relay1
                    struct.pack_into('<ff', mem, 1, 1.0, 0.0)  # Dummy response
                elif cmd == IR_LED_CAMERA_RELAY_OFF:
                    # Toggle IR LED Camera relay state (for example)
                    print("Toggle IR LED Camera Relay OFF command received")
                    relay1_pwm.duty_u16(0)  # Turn OFF relay1
                    struct.pack_into('<ff', mem, 1, 0.0, 0.0)  # Dummy response
                '''
                elif cmd == RASPBERRY_RELAY:
                    # Toggle Raspberry relay state (for example)
                    print("Toggle Raspberry Relay command received")
                    # Here you would add code to actually toggle the relay
                    struct.pack_into('<ff', mem, 1, 1.0, 0.0)  # Dummy response
                '''

                # mark ready for master to read
                mem[0] = READY
            except Exception as e:
                print("Errore assembling response from storage:", e)
            # --- FINE BLOCCO ---

            last = bytes(mem)

        time.sleep(0.1)
except KeyboardInterrupt:
    print("Deinizializzo I2C target")
    i2c.deinit()

