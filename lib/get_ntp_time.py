"""NTP + HTTP time helpers.

Try to obtain current time via NTP; if that's not possible (e.g. no
`getaddrinfo`), fallback to an HTTP API if `api_key` and `timezone` are
provided.

Provides:
- `get_time_ntp(host='pool.ntp.org')` -> RTC tuple or None
- `get_time(api_key=None, timezone=None)` -> RTC tuple or None
- `getTimeNTP(timezone=None, host='pool.ntp.org')` -> RTC tuple or None (compat)
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


def _is_leap_year(year: int) -> bool:
    return (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)


def _days_in_month(year: int, month: int) -> int:
    if month in (1, 3, 5, 7, 8, 10, 12):
        return 31
    if month in (4, 6, 9, 11):
        return 30
    return 29 if _is_leap_year(year) else 28


def _weekday_mon0(year: int, month: int, day: int) -> int:
    """Weekday with Monday=0..Sunday=6 (Sakamoto)."""
    t = [0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4]
    y = year
    if month < 3:
        y -= 1
    # Sakamoto returns Sunday=0..Saturday=6
    w_sun0 = (y + y // 4 - y // 100 + y // 400 + t[month - 1] + day) % 7
    # Convert to Monday=0..Sunday=6
    return (w_sun0 - 1) % 7


def _yearday(year: int, month: int, day: int) -> int:
    yd = 0
    for m in range(1, month):
        yd += _days_in_month(year, m)
    yd += int(day)
    return yd


def _add_hours_to_ymdhms(year, month, day, hour, minute, second, add_hours: int):
    """Add hours and normalize date/time; returns (y,m,d,hh,mm,ss)."""
    y, m, d = int(year), int(month), int(day)
    hh, mm, ss = int(hour), int(minute), int(second)
    hh += int(add_hours)
    while hh >= 24:
        hh -= 24
        d += 1
        dim = _days_in_month(y, m)
        if d > dim:
            d = 1
            m += 1
            if m > 12:
                m = 1
                y += 1
    while hh < 0:
        hh += 24
        d -= 1
        if d < 1:
            m -= 1
            if m < 1:
                m = 12
                y -= 1
            d = _days_in_month(y, m)
    return y, m, d, hh, mm, ss


def _eu_dst_active_utc(y: int, mo: int, d: int, hh: int, mm: int, ss: int) -> bool:
    """EU DST rule in UTC: active from last Sunday of March 01:00 UTC to last Sunday of October 01:00 UTC."""
    # last Sunday of March
    mar_last = _days_in_month(y, 3)
    while _weekday_mon0(y, 3, mar_last) != 6:
        mar_last -= 1
    # last Sunday of October
    oct_last = _days_in_month(y, 10)
    while _weekday_mon0(y, 10, oct_last) != 6:
        oct_last -= 1

    cur = (y, mo, d, hh, mm, ss)
    start = (y, 3, mar_last, 1, 0, 0)
    end = (y, 10, oct_last, 1, 0, 0)
    return cur >= start and cur < end


def ntp_utc_to_europe_rome(ntp_utc_tuple):
    """Convert NTP UTC tuple (Y,M,D,hh,mm,ss,weekday,yearday) to Europe/Rome local time.

    Returns a tuple in the SAME shape: (Y,M,D,hh,mm,ss,weekday,yearday)
    where weekday is Monday=0..Sunday=6.
    """
    if not ntp_utc_tuple or len(ntp_utc_tuple) < 6:
        return ntp_utc_tuple

    y = int(ntp_utc_tuple[0])
    mo = int(ntp_utc_tuple[1])
    d = int(ntp_utc_tuple[2])
    hh = int(ntp_utc_tuple[3])
    mm = int(ntp_utc_tuple[4])
    ss = int(ntp_utc_tuple[5])

    # CET base offset +1, CEST during DST +2
    dst = _eu_dst_active_utc(y, mo, d, hh, mm, ss)
    offset_h = 2 if dst else 1
    ly, lmo, ld, lhh, lmm, lss = _add_hours_to_ymdhms(y, mo, d, hh, mm, ss, offset_h)
    lwd = _weekday_mon0(ly, lmo, ld)
    lyd = _yearday(ly, lmo, ld)
    return (ly, lmo, ld, lhh, lmm, lss, lwd, lyd)


def getTimeNTP(timezone=None, host=NTP_HOST, timeout=1, api_key=None):
    """Compatibility wrapper (camelCase) used by older scripts.

    - Tries NTP first (UTC). If `api_key` is provided, falls back to HTTP using
      the given `timezone` (e.g. 'Europe/Rome').
    - Returns an RTC tuple or None.

    Note: NTP returns UTC; this function does not apply timezone offsets.
    """
    t = get_time_ntp(host=host, timeout=timeout)
    if t is not None:
        return t
    if api_key and timezone:
        return _get_time_ipgeo(api_key, timezone)
    return None