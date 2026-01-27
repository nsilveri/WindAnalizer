from lib.SDL_INA3221_MP import SDL_INA3221
from machine import I2C
from lib.i2c_scanner import scan_i2c

def init_i2c(id=0, scl=1, sda=0):
	return I2C(id, scl=scl, sda=sda)

def init_ina(i2c=None, addr=0x42, scan=True):
	if i2c is None:
		i2c = init_i2c()
	if scan:
		try:
			scan_i2c(i2c)
		except Exception:
			pass

	try:
		ina = SDL_INA3221(i2c, addr=addr)
		return ina
	except Exception as e:
		print("INA3221 Initialization Error:", e)
		return None

def read_bus_voltage(ina, channel=1):
	try:
		return ina.get_bus_voltage(channel)
	except Exception as e:
		print("INA3221 Read Error:", e)
		return None

