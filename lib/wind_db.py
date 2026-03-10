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
