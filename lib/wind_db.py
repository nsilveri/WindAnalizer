import os
import json
from lib import path as libpath


class FileTable:
    """Fallback table that appends JSON lines to a file."""

    def __init__(self, filepath):
        self.filepath = filepath
        # ensure directory exists
        parent = libpath.dirname(filepath)
        if parent and not libpath.exists(parent):
            try:
                libpath.makedirs(parent)
            except Exception:
                pass

    def insert(self, record):
        try:
            with open(self.filepath, 'a') as f:
                f.write(json.dumps(record) + '\n')
            return True
        except Exception as e:
            print('FileTable insert error:', e)
            return False


def _ensure_table_columns(db_path: str, table_name: str, columns: dict) -> bool:
    """Best-effort migration: ensure columns exist in micro_py_database definition.json.

    This is safe to run on every boot; it only edits the definition when needed.
    Returns True if any change was made.
    """
    table_name = (table_name or '').lower()
    definition_path = libpath.join(db_path, table_name, 'definition.json')
    try:
        with open(definition_path, 'r') as f:
            definition = json.loads(f.read() or '{}')
        definition_columns = definition.get('columns') or {}

        changed = False
        for col_name, col_def in columns.items():
            col_key = str(col_name).lower()
            if col_key not in definition_columns:
                definition_columns[col_key] = col_def
                changed = True

        if not changed:
            return False

        definition['columns'] = definition_columns
        with open(definition_path, 'w') as f:
            f.write(json.dumps(definition))
        return True
    except Exception:
        # If anything goes wrong (missing file, permission, etc.) just skip.
        return False


def init_db(db_path='data/wind', table_name='readings'):
    """Try to initialize micro_py_database; if it fails, return a FileTable fallback.

    `path` for micro_py_database is a folder; for FileTable it's a file path
    `data/wind.jsonl`.
    """
    try:
        from lib.micro_py_database.micropydatabase import Database

        # Ensure parent directory exists (Database.create will make the DB folder)
        parent = libpath.dirname(db_path)
        if parent and not libpath.exists(parent):
            try:
                libpath.makedirs(parent)
            except Exception:
                pass

        if not Database.exist(db_path):
            Database.create(db_path)
        db = Database.open(db_path)

        # Defensive check: Database.open should return an object with expected
        # attributes. Some environments may return a module or unexpected
        # object; detect that and fall back to FileTable.
        if not (hasattr(db, 'path') and hasattr(db, 'open_table')):
            print('micro_py_database returned unexpected object:', type(db))
            raise Exception('micro_py_database returned unexpected object')

        # Ensure table exists
        try:
            db.create_table(table_name, ['timestamp', 'windSpeed', 'outOfScale', 'message'])
        except Exception:
            # Table likely exists
            pass

        # If table already exists, it might have been created with an older
        # schema. Ensure new columns are present (best-effort), then reopen.
        _ensure_table_columns(
            db_path,
            table_name,
            {
                'message': {'data_type': 'str', 'max_length': 10000},
            },
        )

        table = db.open_table(table_name)

        # Basic sanity check: table should have insert()
        if hasattr(table, 'insert'):
            return table
        else:
            raise Exception('micro_py_database table missing insert()')

    except Exception as e:
        print('micro_py_database unavailable or failed:', e)
        # Fallback: use a simple JSONL file table
        jsonl_path = libpath.join('data', table_name + '.jsonl')
        return FileTable(jsonl_path)


def insert_record(tbl, timestamp, wind_speed, out_of_scale, message=None):
    if tbl is None:
        return

    try:
        # Normalize field names to lowercase (micro_py_database stores columns lowercased)
        # and avoid inserting None for typed columns by converting to string when needed.
        record = {
            'timestamp': str(timestamp) if timestamp is not None else '',
            'windspeed': '' if wind_speed is None else str(wind_speed),
            'outofscale': str(bool(out_of_scale)),
            'message': '' if message is None else str(message),
        }

        # micro_py_database validates columns strictly; if the table is missing
        # newer columns, drop them to avoid failing the whole insert.
        if hasattr(tbl, 'columns') and isinstance(getattr(tbl, 'columns'), dict):
            allowed = set(k.lower() for k in tbl.columns.keys())
            record = {k: v for k, v in record.items() if k.lower() in allowed}

        tbl.insert(record)
    except Exception as e:
        print('Failed to insert record:', e)


def get_latest_record(tbl):
    """Return the latest record dict or None.

    Supports micro_py_database Table and the FileTable fallback.
    """
    if tbl is None:
        return None

    # micro_py_database Table
    if hasattr(tbl, 'current_row') and hasattr(tbl, 'find_row'):
        try:
            row_id = int(getattr(tbl, 'current_row', 0) or 0)
            if row_id <= 0:
                return None
            return tbl.find_row(row_id).get('d')
        except Exception:
            return None

    # FileTable fallback (JSONL)
    if hasattr(tbl, 'filepath'):
        try:
            last = None
            with open(tbl.filepath, 'r') as f:
                for line in f:
                    if line and line.strip():
                        last = line
            if not last:
                return None
            return json.loads(last)
        except Exception:
            return None

    return None


def iter_last_records(tbl, n=5):
    """Yield up to the last n records (oldest->newest)."""
    if tbl is None:
        return
    if n is None or n <= 0:
        return

    # micro_py_database Table
    if hasattr(tbl, 'current_row') and hasattr(tbl, 'find_row'):
        try:
            current_row = int(getattr(tbl, 'current_row', 0) or 0)
            start_row = current_row - int(n) + 1
            if start_row < 1:
                start_row = 1
            for row_id in range(start_row, current_row + 1):
                try:
                    rec = tbl.find_row(row_id).get('d')
                    if rec is not None:
                        yield rec
                except Exception:
                    continue
            return
        except Exception:
            return

    # FileTable fallback (JSONL)
    if hasattr(tbl, 'filepath'):
        try:
            # Keep only last n lines with a small ring buffer.
            buf = [None] * int(n)
            idx = 0
            count = 0
            with open(tbl.filepath, 'r') as f:
                for line in f:
                    if not line or not line.strip():
                        continue
                    buf[idx] = line
                    idx = (idx + 1) % int(n)
                    count += 1
            if count == 0:
                return
            take = int(n) if count >= int(n) else count
            start = idx if count >= int(n) else 0
            for i in range(take):
                line = buf[(start + i) % int(n)]
                if line:
                    try:
                        yield json.loads(line)
                    except Exception:
                        pass
        except Exception:
            return


def _to_float(v):
    try:
        return float(v)
    except Exception:
        return None


def _to_bool(v):
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    s = str(v).strip().lower()
    return s in ('1', 'true', 't', 'yes', 'y')


def format_timestamp(ts):
    """Format a timestamp in a human-readable way.

    Accepts:
    - epoch seconds (int/float or numeric string)
    - RTC tuples/lists like (y,m,d,wd,hh,mm,ss,sub)
    Returns a string.
    """
    if ts is None:
        return ''

    # RTC-like tuple/list
    if isinstance(ts, (tuple, list)) and len(ts) >= 7:
        try:
            y, m, d, wd, hh, mm, ss = ts[0], ts[1], ts[2], ts[3], ts[4], ts[5], ts[6]
            return '{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}'.format(int(y), int(m), int(d), int(hh), int(mm), int(ss))
        except Exception:
            return str(ts)

    # Epoch seconds
    try:
        t = float(ts) if not isinstance(ts, (int, float)) else ts
        try:
            import utime as time
        except Exception:
            import time
        lt = time.localtime(int(t))
        return '{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}'.format(lt[0], lt[1], lt[2], lt[3], lt[4], lt[5])
    except Exception:
        return str(ts)


def summarize_records(records):
    """Return a compact human-readable summary for Telegram."""
    if not records:
        return 'no data'

    count = 0
    count_speed = 0
    count_oos = 0
    min_ws = None
    max_ws = None
    sum_ws = 0.0
    last_ts = None

    for r in records:
        if not isinstance(r, dict):
            continue
        count += 1
        last_ts = r.get('timestamp', last_ts)
        ws = _to_float(r.get('windspeed'))
        if ws is not None:
            count_speed += 1
            sum_ws += ws
            if min_ws is None or ws < min_ws:
                min_ws = ws
            if max_ws is None or ws > max_ws:
                max_ws = ws
        if _to_bool(r.get('outofscale')):
            count_oos += 1

    avg_ws = (sum_ws / count_speed) if count_speed else None
    parts = [f'n={count}']
    if avg_ws is not None:
        parts.append(f'avg={avg_ws:.2f}')
    if min_ws is not None:
        parts.append(f'min={min_ws:.2f}')
    if max_ws is not None:
        parts.append(f'max={max_ws:.2f}')
    parts.append(f'oos={count_oos}')
    if last_ts is not None:
        parts.append('last_ts={}'.format(format_timestamp(last_ts)))
    return ' '.join(parts)


def _parse_epoch_seconds(ts):
    """Best-effort parse of stored timestamp into float seconds."""
    if ts is None:
        return None
    if isinstance(ts, (int, float)):
        return float(ts)
    try:
        s = str(ts).strip()
        # We store epoch as str(time.time()), so this is usually numeric.
        return float(s)
    except Exception:
        return None


def get_records_since(tbl, since_epoch, max_scan=5000):
    """Collect records with timestamp >= since_epoch.

    Scans backwards from the newest rows (best-effort) and stops when data is
    older than the cutoff or when max_scan is reached.

    Returns a list of record dicts ordered oldest->newest.
    """
    if tbl is None:
        return []

    since_epoch = float(since_epoch)

    # micro_py_database Table
    if hasattr(tbl, 'current_row') and hasattr(tbl, 'find_row'):
        try:
            current_row = int(getattr(tbl, 'current_row', 0) or 0)
        except Exception:
            current_row = 0
        out = []
        scanned = 0
        row_id = current_row
        while row_id >= 1 and scanned < int(max_scan):
            scanned += 1
            try:
                rec = tbl.find_row(row_id).get('d')
            except Exception:
                row_id -= 1
                continue
            ts = _parse_epoch_seconds(rec.get('timestamp')) if isinstance(rec, dict) else None
            if ts is not None and ts < since_epoch:
                break
            if isinstance(rec, dict):
                out.append(rec)
            row_id -= 1
        out.reverse()
        return out

    # FileTable fallback (JSONL)
    if hasattr(tbl, 'filepath'):
        try:
            # Read last max_scan lines into a buffer.
            buf = [None] * int(max_scan)
            idx = 0
            count = 0
            with open(tbl.filepath, 'r') as f:
                for line in f:
                    if not line or not line.strip():
                        continue
                    buf[idx] = line
                    idx = (idx + 1) % int(max_scan)
                    count += 1

            take = int(max_scan) if count >= int(max_scan) else count
            start = idx if count >= int(max_scan) else 0
            out = []
            for i in range(take):
                line = buf[(start + i) % int(max_scan)]
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                ts = _parse_epoch_seconds(rec.get('timestamp')) if isinstance(rec, dict) else None
                if ts is None or ts < since_epoch:
                    continue
                out.append(rec)
            # Already oldest->newest because we iterated forward.
            return out
        except Exception:
            return []

    return []


def iter_records_since_newest(tbl, since_epoch, max_scan=5000):
    """Yield records with timestamp >= since_epoch, newest->oldest.

    This avoids building large lists in RAM (useful on MicroPython).
    Best-effort: stops scanning when it encounters a record older than cutoff.
    """
    if tbl is None:
        return

    since_epoch = float(since_epoch)

    # micro_py_database Table
    if hasattr(tbl, 'current_row') and hasattr(tbl, 'find_row'):
        try:
            current_row = int(getattr(tbl, 'current_row', 0) or 0)
        except Exception:
            current_row = 0
        scanned = 0
        row_id = current_row
        while row_id >= 1 and scanned < int(max_scan):
            scanned += 1
            try:
                rec = tbl.find_row(row_id).get('d')
            except Exception:
                row_id -= 1
                continue
            ts = _parse_epoch_seconds(rec.get('timestamp')) if isinstance(rec, dict) else None
            if ts is not None and ts < since_epoch:
                break
            if isinstance(rec, dict):
                yield rec
            row_id -= 1
        return

    # FileTable fallback (JSONL)
    if hasattr(tbl, 'filepath'):
        try:
            # Keep only last max_scan lines (ring buffer), then yield reverse.
            buf = [None] * int(max_scan)
            idx = 0
            count = 0
            with open(tbl.filepath, 'r') as f:
                for line in f:
                    if not line or not line.strip():
                        continue
                    buf[idx] = line
                    idx = (idx + 1) % int(max_scan)
                    count += 1

            take = int(max_scan) if count >= int(max_scan) else count
            start = idx if count >= int(max_scan) else 0
            # Iterate newest->oldest
            for j in range(take - 1, -1, -1):
                line = buf[(start + j) % int(max_scan)]
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                ts = _parse_epoch_seconds(rec.get('timestamp')) if isinstance(rec, dict) else None
                if ts is not None and ts < since_epoch:
                    break
                if isinstance(rec, dict):
                    yield rec
        except Exception:
            return

