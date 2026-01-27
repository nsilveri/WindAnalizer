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
            db.create_table(table_name, ['timestamp', 'windSpeed', 'outOfScale'])
        except Exception:
            # Table likely exists
            pass

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


def insert_record(tbl, timestamp, wind_speed, out_of_scale):
    if tbl is None:
        return

    try:
        # Normalize field names to lowercase (micro_py_database stores columns lowercased)
        # and avoid inserting None for typed columns by converting to string when needed.
        record = {
            'timestamp': str(timestamp) if timestamp is not None else '',
            'windspeed': '' if wind_speed is None else str(wind_speed),
            'outofscale': str(bool(out_of_scale)),
        }
        tbl.insert(record)
    except Exception as e:
        print('Failed to insert record:', e)
