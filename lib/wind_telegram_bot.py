"""Telegram bot integration for WindAnalizer.

Designed for MicroPython on Pico W.
Uses the bundled micropython-telegram-bot (telegram.py) via sys.path.

Commands:
- /help
- /status              -> current/latest reading
- /last [n]            -> last n readings (default 5, max 20)
- /stats [n]           -> min/avg/max over last n readings (default 60, max 1000)

The bot reads from the DB table passed in (micro_py_database Table) or the
FileTable fallback (JSONL) provided by lib.wind_db.
"""

from lib.wind_db import get_latest_record, iter_last_records, summarize_records, format_timestamp, iter_records_since_newest
from lib.get_ntp_time import getTimeNTP, ntp_utc_to_europe_rome


_WEEKDAYS_IT = ['Lun', 'Mar', 'Mer', 'Gio', 'Ven', 'Sab', 'Dom']


def _weekday_it(wd):
    try:
        wd_i = int(wd)
    except Exception:
        return ''

    # DS1302 often uses 1..7, while utime/localtime uses 0..6 (Mon=0).
    if 1 <= wd_i <= 7:
        wd_i = wd_i - 1
    if 0 <= wd_i <= 6:
        return _WEEKDAYS_IT[wd_i]
    return ''


def _pretty_dt(ts):
    """Return a more readable timestamp string with weekday when possible."""
    base = format_timestamp(ts)
    wd = None
    try:
        if isinstance(ts, (tuple, list)):
            # DS1302: [Y,M,D,wd,hh,mm,ss]
            # machine.RTC: (Y,M,D,wd,hh,mm,ss,sub)
            if len(ts) >= 4:
                wd = ts[3]
    except Exception:
        wd = None

    wd_name = _weekday_it(wd) if wd is not None else ''
    if wd_name and base:
        return '{} {}'.format(wd_name, base)
    return base


def _shorten(s, max_len=300):
    try:
        s = '' if s is None else str(s)
    except Exception:
        return ''
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + '…'


def _set_machine_rtc_from_ds(dt):
    """Set MicroPython internal RTC from a DS1302-style datetime list.

    DS1302 date_time() format: [Y, M, D, weekday, hh, mm, ss]
    machine.RTC().datetime() format: (Y, M, D, weekday, hh, mm, ss, subseconds)
    """
    try:
        if not dt or len(dt) < 7:
            return False
        y, m, d, wd, hh, mm, ss = int(dt[0]), int(dt[1]), int(dt[2]), int(dt[3]), int(dt[4]), int(dt[5]), int(dt[6])
        import machine
        machine.RTC().datetime((y, m, d, wd, hh, mm, ss, 0))
        return True
    except Exception:
        return False


def _record_key_for_display(rec):
    """Key used to collapse duplicate records in /last output."""
    if not isinstance(rec, dict):
        return None
    ts_raw = rec.get('timestamp', '')
    ts = format_timestamp(ts_raw) if ts_raw != '' else ''
    ws = rec.get('windspeed', '')
    oos = rec.get('outofscale', '')
    msg = rec.get('message', '')
    return (ts, str(ws), str(oos), str(msg))


def _parse_int(s, default):
    try:
        return int(s)
    except Exception:
        return default


def _urlquote(s):
    # Minimal URL-encoding for query param values.
    try:
        b = s.encode('utf-8')
    except Exception:
        b = str(s).encode('utf-8')
    out = []
    for c in b:
        if (48 <= c <= 57) or (65 <= c <= 90) or (97 <= c <= 122) or c in (45, 46, 95, 126):
            out.append(chr(c))
        else:
            out.append('%{:02X}'.format(c))
    return ''.join(out)


def _to_float(v):
    try:
        return float(v)
    except Exception:
        return None


def _csv_escape(v):
    try:
        s = '' if v is None else str(v)
    except Exception:
        s = ''
    # RFC4180-ish: quote if it contains special chars.
    if any(ch in s for ch in (',', '"', '\n', '\r')):
        s = '"' + s.replace('"', '""') + '"'
    return s


def _build_quickchart_url(values, width=600, height=300):
    # values: list of numbers or None
    # Chart.js v2 config (QuickChart default)
    cfg = {
        'type': 'line',
        'data': {
            'datasets': [
                {
                    'label': 'Wind (m/s)',
                    'data': values,
                    'fill': False,
                    'spanGaps': False,
                    'lineTension': 0,
                    'pointRadius': 0,
                }
            ]
        },
        'options': {
            'legend': {'display': False},
            'scales': {
                'xAxes': [{'display': False}],
                'yAxes': [{'ticks': {'beginAtZero': True}}],
            },
        }
    }

    try:
        import ujson as json
    except Exception:
        import json

    c = json.dumps(cfg)

    # Use base64 to keep the URL shorter and avoid heavy % encoding.
    try:
        import ubinascii as binascii
        b64 = binascii.b2a_base64(c.encode('utf-8')).strip().decode('ascii')
    except Exception:
        try:
            import binascii
            b64 = binascii.b2a_base64(c.encode('utf-8')).strip().decode('ascii')
        except Exception:
            b64 = None

    if b64:
        return 'https://quickchart.io/chart?format=png&backgroundColor=white&width={}&height={}&encoding=base64&c={}'.format(
            int(width), int(height), _urlquote(b64)
        )

    # Fallback: percent-encode JSON.
    return 'https://quickchart.io/chart?format=png&backgroundColor=white&width={}&height={}&c={}'.format(
        int(width), int(height), _urlquote(c)
    )


class WindTelegramBot:
    def __init__(self, token, db_table, state, allowed_chat_ids=None, debug=False):
        self.db_table = db_table
        self.state = state
        self.allowed_chat_ids = allowed_chat_ids
        self.debug = debug

        # Make bundled telegram.py importable even if the folder name has '-'
        try:
            import sys
            for p in ('/lib/micropython-telegram-bot', 'lib/micropython-telegram-bot'):
                if p not in sys.path:
                    sys.path.append(p)
        except Exception:
            pass

        from telegram import TelegramBot

        self._bot = TelegramBot(token, self._on_message)
        self._bot.debug = bool(debug)

    def _is_allowed(self, chat_id):
        if not self.allowed_chat_ids:
            return True
        try:
            return int(chat_id) in set(int(x) for x in self.allowed_chat_ids)
        except Exception:
            return False

    def _reply(self, chat_id, text):
        try:
            self._bot.send(chat_id, text)
        except Exception:
            pass

    def _format_record(self, rec):
        if not rec:
            return 'no data'
        ts_raw = rec.get('timestamp', '')
        ts = format_timestamp(ts_raw) if ts_raw != '' else ''
        ws = rec.get('windspeed', '')
        oos = rec.get('outofscale', '')
        if oos == '':
            oos = rec.get('outofscale', '')
        msg = rec.get('message', '')
        parts = []
        if ts:
            parts.append(f"ora={ts}")
        parts.append(f"wind speed={ws}m/s")
        parts.append(f"out of scale={oos}")
        if msg:
            parts.append(f"msg={msg}")
        return ' '.join(parts)

    def _format_record_block(self, rec):
        """Multi-line formatting (used by /last) to make message more readable."""
        if not rec:
            return 'no data'
        ts_raw = rec.get('timestamp', '')
        ts = format_timestamp(ts_raw) if ts_raw != '' else ''
        ws = rec.get('windspeed', '')
        oos = rec.get('outofscale', '')
        msg = rec.get('message', '')

        lines = []
        if ts:
            lines.append('ts: {}'.format(ts))
        lines.append('ws: {}'.format(ws))
        lines.append('oos: {}'.format(oos))
        if msg:
            lines.append('msg: {}'.format(_shorten(msg)))
        return '\n'.join(lines)

    def _on_message(self, bot, msg_type, chat_name, sender_name, chat_id, text, entry):
        if not self._is_allowed(chat_id):
            return

        text = (text or '').strip()
        if not text:
            return

        if text.startswith('/start') or text.startswith('/help'):
            self._reply(chat_id, 'Comandi: /status, /last [n], /stats [n], /chart6, /chart24, /csv6, /csv24, /rtc, /sync_rtc, /chatid')
            return

        if text.startswith('/chatid'):
            who = sender_name or 'unknown'
            cname = chat_name or ''
            self._reply(chat_id, f'chat_id={chat_id} user={who} chat={cname}'.strip())
            return

        if text.startswith('/status'):
            # Prefer in-memory latest (updated by main loop) if present.
            rec = None
            try:
                rec = self.state.get('latest_record')
            except Exception:
                rec = None
            if not rec:
                rec = get_latest_record(self.db_table)
            self._reply(chat_id, self._format_record(rec))
            return

        if text.startswith('/last'):
            parts = text.split()
            n = _parse_int(parts[1], 5) if len(parts) > 1 else 5
            if n < 1:
                n = 1
            if n > 50:
                n = 50
            recs = list(iter_last_records(self.db_table, n))
            if not recs:
                self._reply(chat_id, 'no data')
                return

            # Collapse consecutive duplicates to avoid spam.
            grouped = []  # list of (count, record)
            last_key = None
            last_rec = None
            count = 0
            for r in recs:
                k = _record_key_for_display(r)
                if k is not None and k == last_key:
                    count += 1
                else:
                    if last_rec is not None:
                        grouped.append((count, last_rec))
                    last_key = k
                    last_rec = r
                    count = 1
            if last_rec is not None:
                grouped.append((count, last_rec))

            blocks = []
            idx = 1
            for c, r in grouped:
                header = '#{}'.format(idx)
                if c > 1:
                    header = '{} (x{})'.format(header, c)
                blocks.append('{}\n{}'.format(header, self._format_record_block(r)))
                idx += 1

            self._reply(chat_id, '\n\n'.join(blocks))
            return

        if text.startswith('/stats'):
            parts = text.split()
            n = _parse_int(parts[1], 60) if len(parts) > 1 else 60
            if n < 1:
                n = 1
            if n > 1000:
                n = 1000
            recs = list(iter_last_records(self.db_table, n))
            if not recs:
                self._reply(chat_id, 'no data')
                return
            summary = summarize_records(recs)
            self._reply(chat_id, summary)
            return

        if text.startswith('/csv6') or text.startswith('/csv24'):
            try:
                try:
                    import gc
                    gc.collect()
                except Exception:
                    pass

                try:
                    import time
                except Exception:
                    import utime as time

                hours = 6 if text.startswith('/csv6') else 24
                now = time.time()
                since = now - (hours * 60 * 60)
                # Filename + path on filesystem (avoid keeping CSV in RAM)
                try:
                    lt = time.localtime(int(now))
                    fname = 'wind_{}h_{:04d}{:02d}{:02d}_{:02d}{:02d}{:02d}.csv'.format(hours, lt[0], lt[1], lt[2], lt[3], lt[4], lt[5])
                except Exception:
                    fname = 'wind_{}h.csv'.format(hours)

                try:
                    import uos as os
                except Exception:
                    import os

                export_dir = 'data/exports'
                try:
                    os.mkdir('data')
                except Exception:
                    pass
                try:
                    os.mkdir(export_dir)
                except Exception:
                    pass
                file_path = export_dir + '/' + fname

                # Generate CSV incrementally
                max_rows = 1000
                wrote = 0
                truncated = False
                try:
                    f = open(file_path, 'w')
                    f.write('epoch,timestamp,windspeed,outofscale,message\n')
                    for r in iter_records_since_newest(self.db_table, since_epoch=since, max_scan=20000):
                        if not isinstance(r, dict):
                            continue
                        epoch = r.get('timestamp', '')
                        ts = format_timestamp(epoch) if epoch != '' else ''
                        ws = r.get('windspeed', '')
                        oos = r.get('outofscale', '')
                        msg = r.get('message', '')
                        line = '{},{},{},{},{}\n'.format(
                            _csv_escape(epoch),
                            _csv_escape(ts),
                            _csv_escape(ws),
                            _csv_escape(oos),
                            _csv_escape(msg),
                        )
                        f.write(line)
                        wrote += 1
                        if wrote % 200 == 0:
                            try:
                                import gc
                                gc.collect()
                            except Exception:
                                pass
                        if wrote >= max_rows:
                            truncated = True
                            break
                finally:
                    try:
                        f.close()
                    except Exception:
                        pass

                if wrote <= 0:
                    self._reply(chat_id, 'Nessun dato nelle ultime {}h'.format(hours))
                    return

                caption = 'CSV wind ultime {}h (righe={})'.format(hours, wrote)
                if truncated:
                    caption += ' [TRONCATO]'

                try:
                    self._bot.send_document_file(chat_id, file_path, filename=fname, mime_type='text/csv', caption=caption)
                except Exception as e:
                    self._reply(chat_id, 'csv error: {}'.format(e))
            except Exception as e:
                self._reply(chat_id, 'csv error: {}'.format(e))
            return

        if text.startswith('/chart6') or text.startswith('/chart24') or text.startswith('/chart'):
            # Chart of last 6/24 hours windspeed
            try:
                try:
                    import gc
                    gc.collect()
                except Exception:
                    pass

                try:
                    import time
                except Exception:
                    import utime as time

                now = time.time()

                hours = 24
                if text.startswith('/chart6'):
                    hours = 6
                since = now - (hours * 60 * 60)
                # Stream records to keep memory low.
                points = []
                seen = 0
                for r in iter_records_since_newest(self.db_table, since_epoch=since, max_scan=20000):
                    if not isinstance(r, dict):
                        continue
                    ws = _to_float(r.get('windspeed'))
                    points.append(ws)
                    seen += 1
                    # Keep bounded by repeatedly decimating.
                    max_points = 48
                    while len(points) > max_points:
                        points = points[::2]
                    if seen % 250 == 0:
                        try:
                            import gc
                            gc.collect()
                        except Exception:
                            pass

                if not points:
                    self._reply(chat_id, 'Nessun dato windspeed nelle ultime {}h'.format(hours))
                    return

                # We iterated newest->oldest; reverse for chart left-to-right.
                try:
                    points.reverse()
                except Exception:
                    pass

                url = _build_quickchart_url(points)

                # Caption with quick stats
                vals = [p for p in points if isinstance(p, (int, float))]
                if vals:
                    mn = min(vals)
                    mx = max(vals)
                    av = sum(vals) / len(vals)
                    caption = 'Wind ultime {}h (campioni={})\nmin={:.2f} avg={:.2f} max={:.2f}'.format(hours, len(points), mn, av, mx)
                else:
                    caption = 'Wind ultime {}h (campioni={})'.format(hours, len(points))

                # Send as photo
                try:
                    self._bot.send_photo(chat_id, url, caption=caption)
                except Exception:
                    # Fallback: send link
                    self._reply(chat_id, caption + '\n' + url)
            except Exception as e:
                self._reply(chat_id, 'chart24 error: {}'.format(e))
            return
        
        if text.startswith('/rtc'):
            try:
                blocks = []

                tz_name = ''
                try:
                    tz_name = self.state.get('timezone') if isinstance(self.state, dict) else ''
                except Exception:
                    tz_name = ''

                # External DS1302 (if provided by main via state)
                try:
                    ext = self.state.get('rtc') if isinstance(self.state, dict) else None
                    if ext and hasattr(ext, 'date_time'):
                        ext_dt = ext.date_time()
                        suffix = 'local' + (f' ({tz_name})' if tz_name else '')
                        blocks.append('DS1302\n{}\n[{}]'.format(_pretty_dt(ext_dt), suffix))
                except Exception:
                    pass

                # Internal MicroPython RTC
                try:
                    import machine
                    int_dt = machine.RTC().datetime()
                    suffix = 'local' + (f' ({tz_name})' if tz_name else '')
                    blocks.append('machine.RTC\n{}\n[{}]'.format(_pretty_dt(int_dt), suffix))
                except Exception:
                    pass
                
                # NTP time (if provided by main via state)
                try:
                    st = self.state if isinstance(self.state, dict) else None
                    ntp_utc = st.get('ntp_time_utc') if st else None
                    ntp_local = st.get('ntp_time_local') if st else None
                    if ntp_utc or ntp_local:
                        lines = []
                        if ntp_utc:
                            lines.append('UTC: {}'.format(format_timestamp((ntp_utc[0], ntp_utc[1], ntp_utc[2], ntp_utc[6], ntp_utc[3], ntp_utc[4], ntp_utc[5]))))
                        if ntp_local:
                            lines.append('Local: {}'.format(format_timestamp((ntp_local[0], ntp_local[1], ntp_local[2], ntp_local[6], ntp_local[3], ntp_local[4], ntp_local[5]))))
                        blocks.append('NTP\n{}\n[UTC->local]'.format('\n'.join(lines)))
                except Exception:
                    pass

                if not blocks:
                    self._reply(chat_id, 'RTC: unavailable')
                else:
                    self._reply(chat_id, '\n\n'.join(blocks))
            except Exception as e:
                self._reply(chat_id, f'RTC error: {e}')
            return

        if text.startswith('/sync_rtc'):
            # Sync DS1302 + machine.RTC from NTP (when available)
            try:
                st = self.state if isinstance(self.state, dict) else None
                tz_name = st.get('timezone') if st else ''
                ext = st.get('rtc') if st else None

                if not ext or not hasattr(ext, 'date_time'):
                    self._reply(chat_id, 'sync_rtc error: DS1302 not available')
                    return

                # NTP fetch is UTC
                ntp_utc = getTimeNTP(tz_name)
                if not ntp_utc:
                    self._reply(chat_id, 'sync_rtc error: NTP not available')
                    return

                # Convert to local time (Europe/Rome supported)
                if tz_name == 'Europe/Rome':
                    ntp_local = ntp_utc_to_europe_rome(ntp_utc)
                else:
                    ntp_local = ntp_utc

                # Build DS1302 datetime list: [Y,M,D,weekday,hh,mm,ss]
                y, m, d = int(ntp_local[0]), int(ntp_local[1]), int(ntp_local[2])
                hh, mm, ss = int(ntp_local[3]), int(ntp_local[4]), int(ntp_local[5])
                wd = int(ntp_local[6])
                ds_dt = [y, m, d, wd, hh, mm, ss]

                # Set DS1302 and internal RTC
                ext.date_time(ds_dt)
                _set_machine_rtc_from_ds(ds_dt)

                # Update state for /rtc display
                try:
                    st['ntp_time_utc'] = ntp_utc
                    st['ntp_time_local'] = ntp_local
                    st['ntp_ds_dt_local'] = ds_dt
                except Exception:
                    pass

                msg = 'sync_rtc OK\nUTC: {}\nLocal{}: {}'\
                    .format(
                        format_timestamp((ntp_utc[0], ntp_utc[1], ntp_utc[2], ntp_utc[6], ntp_utc[3], ntp_utc[4], ntp_utc[5])),
                        f' ({tz_name})' if tz_name else '',
                        format_timestamp((ntp_local[0], ntp_local[1], ntp_local[2], ntp_local[6], ntp_local[3], ntp_local[4], ntp_local[5])),
                    )
                self._reply(chat_id, msg)
            except Exception as e:
                self._reply(chat_id, 'sync_rtc error: {}'.format(e))
            return

        # Unknown command
        if text.startswith('/'):
            self._reply(chat_id, 'Comando non riconosciuto. Usa /help')

    def poll(self):
        """Run a single non-blocking poll step.

        Call this periodically from your main loop.
        """
        try:
            # Inline the run() loop step-by-step to avoid needing uasyncio.
            if self._bot.reconnect:
                try:
                    import socket, ssl
                    addr = socket.getaddrinfo('api.telegram.org', 443, socket.AF_INET)
                    addr = addr[0][-1]
                    self._bot.socket = socket.socket(socket.AF_INET)
                    self._bot.socket.connect(addr)
                    self._bot.socket.setblocking(False)
                    self._bot.ssl = ssl.wrap_socket(self._bot.socket)
                    self._bot.reconnect = False
                    self._bot.pending = False
                except Exception:
                    self._bot.reconnect = True

            self._bot.send_api_requests()
            self._bot.read_api_response()

            # Watchdog: if a request is pending for too long, reconnect.
            try:
                import time
                if getattr(self._bot, 'pending', False):
                    if time.ticks_diff(time.ticks_ms(), getattr(self._bot, 'pending_since', 0)) > getattr(self._bot, 'watchdog_timeout_ms', 60000):
                        self._bot.reconnect = True
            except Exception:
                pass
        except Exception:
            # Any unexpected issue: force reconnect next time.
            try:
                self._bot.reconnect = True
            except Exception:
                pass

    @property
    def bot(self):
        return self._bot
