from machine import I2C

def scan_i2c(i2c=I2C(0, scl=1, sda=0)):
    try:
        devices = i2c.scan()
        if devices:
            print("I2C devices found:", ", ".join("0x{:02X}".format(d) for d in devices))
        else:
            print("No I2C devices found.")
    except Exception as e:
        print("I2C scan error:", e)