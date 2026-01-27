import network
wlan = network.WLAN(network.STA_IF)
wlan.active(True)

def scan():
    networks = wlan.scan()
    ssids = [net[0].decode('utf-8') for net in networks]
    return ssids

def connect(ssid, password):
    if not wlan.isconnected():
        wlan.connect(ssid, password)
        while not wlan.isconnected():
            pass
    return wlan.ifconfig()