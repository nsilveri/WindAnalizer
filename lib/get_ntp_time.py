"""NTP + HTTP time helpers.

Try to obtain current time via NTP; if that's not possible (e.g. no
`getaddrinfo`), fallback to an HTTP API if `api_key` and `timezone` are
provided.

Provides:
- `get_time_ntp(host='pool.ntp.org')` -> RTC tuple or None
- `get_time(api_key=None, timezone=None)` -> RTC tuple or None
"""

try:
    import socket
except Exception:
    import usocket as socket

try:
    import ustruct as struct
except Exception:
    import struct

try:
    import utime as time
except Exception:
    import time

NTP_HOST = 'pool.ntp.org'


def get_time_ntp(host=NTP_HOST, timeout=1):
    NTP_DELTA = 2208988800
    NTP_QUERY = bytearray(48)
    NTP_QUERY[0] = 0x1B

    try:
        getaddr = getattr(socket, 'getaddrinfo', None)
        if getaddr is None:
            raise AttributeError('getaddrinfo not available')

        addr = getaddr(host, 123)[0][-1]
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Some MicroPython builds use settimeout on sockets
            try:
                s.settimeout(timeout)
            except Exception:
                pass
            s.sendto(NTP_QUERY, addr)
            msg = s.recv(48)
        finally:
            try:
                s.close()
            except Exception:
                pass

        if not msg or len(msg) < 48:
            return None

        ntp_time = struct.unpack("!I", msg[40:44])[0]
        return time.gmtime(ntp_time - NTP_DELTA)

    except Exception as e:
        # Caller can decide to fallback to HTTP
        print('NTP failed:', e)
        return None


def _get_time_ipgeo(api_key, timezone):
    try:
        try:
            import urequests as requests
        except Exception:
            import requests

        url = 'http://api.ipgeolocation.io/timezone?apiKey={}&tz={}'.format(api_key, timezone)
        resp = requests.get(url)
        data = resp.json()
        try:
            resp.close()
        except Exception:
            pass

        dt = data.get('date_time')
        if not dt or ' ' not in dt:
            return None
        date_str, time_str = dt.split(' ')
        y, m, d = [int(x) for x in date_str.split('-')]
        hh, mm, ss = [int(x) for x in time_str.split(':')]
        weekday = int(data.get('day_of_week', 0))
        return (y, m, d, weekday, hh, mm, ss, 0)
    except Exception as e:
        print('IPGeo time failed:', e)
        return None


def get_time(api_key=None, timezone=None):
    """Try NTP first, then HTTP IP Geolocation if provided.

    Returns an RTC tuple or None.
    """
    t = get_time_ntp()
    if t is not None:
        return t
    if api_key and timezone:
        return _get_time_ipgeo(api_key, timezone)
    return None