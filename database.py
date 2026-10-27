from __future__ import annotations
import sqlite3
from pathlib import Path
from contextlib import contextmanager
import pandas as pd

ROOT = Path(__file__).resolve().parent
DEFAULT_DB = ROOT / "data" / "health_diary.sqlite3"

SCHEMA = """
CREATE TABLE IF NOT EXISTS daily (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 record_date TEXT NOT NULL UNIQUE,
 bedtime TEXT, wake_time TEXT, sleep_hours REAL, sleep_quality REAL,
 sleep_notes TEXT, water_ml REAL, physical_activity TEXT, stress_level REAL,
 menstrual_cycle TEXT, lifestyle_notes TEXT,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS meals (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 record_date TEXT NOT NULL, consumed_time TEXT, category TEXT, name TEXT,
 amount TEXT, caffeine TEXT, water_ml REAL, notes TEXT,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS symptoms (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 record_date TEXT NOT NULL, onset_time TEXT, end_time TEXT, main_symptom TEXT NOT NULL,
 severity REAL, dizziness REAL, headache REAL, nausea REAL, associated TEXT,
 potential_triggers TEXT, interfered TEXT, helped TEXT, notes TEXT,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS medications (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 record_date TEXT NOT NULL, name TEXT NOT NULL, dose TEXT, taken_time TEXT,
 reason TEXT, followed_instructions TEXT, reported_effect TEXT, side_effects TEXT,
 notes TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_meals_date ON meals(record_date);
CREATE INDEX IF NOT EXISTS idx_symptoms_date ON symptoms(record_date);
CREATE INDEX IF NOT EXISTS idx_meds_date ON medications(record_date);
"""

@contextmanager
def connect(db_path=DEFAULT_DB):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()

def init_db(db_path=DEFAULT_DB):
    with connect(db_path) as con:
        con.executescript(SCHEMA)

def _clean(row):
    return {k: (None if pd.isna(v) else v) for k, v in row.items()}

def insert_record(table, data, db_path=DEFAULT_DB):
    allowed = {"daily", "meals", "symptoms", "medications"}
    if table not in allowed: raise ValueError("Unsupported table")
    data = _clean(data)
    cols = list(data)
    with connect(db_path) as con:
        cur = con.execute(f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})",
                          [data[c] for c in cols])
        return cur.lastrowid

def upsert_daily(data, db_path=DEFAULT_DB):
    data = _clean(data)
    cols = list(data)
    updates = [c for c in cols if c != "record_date"]
    sql = f"""INSERT INTO daily ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})
              ON CONFLICT(record_date) DO UPDATE SET {','.join(f'{c}=excluded.{c}' for c in updates)},
              updated_at=CURRENT_TIMESTAMP"""
    with connect(db_path) as con: con.execute(sql, [data[c] for c in cols])

def fetch_records(table, start=None, end=None, db_path=DEFAULT_DB):
    if table not in {"daily", "meals", "symptoms", "medications"}: raise ValueError("Unsupported table")
    sql, params = f"SELECT * FROM {table}", []
    if start and end:
        sql += " WHERE record_date BETWEEN ? AND ?"; params = [str(start), str(end)]
    sql += " ORDER BY record_date DESC, id DESC"
    with connect(db_path) as con:
        return pd.read_sql_query(sql, con, params=params)

def update_record(table, record_id, data, db_path=DEFAULT_DB):
    if table not in {"meals", "symptoms", "medications"}: raise ValueError("Unsupported table")
    data = _clean(data)
    with connect(db_path) as con:
        assignments = ",".join(f"{k}=?" for k in data)
        cur = con.execute(f"UPDATE {table} SET {assignments} WHERE id=?", [*data.values(), int(record_id)])
        return cur.rowcount

def delete_record(table, record_id, db_path=DEFAULT_DB):
    if table not in {"meals", "symptoms", "medications"}: raise ValueError("Unsupported table")
    with connect(db_path) as con:
        cur = con.execute(f"DELETE FROM {table} WHERE id=?", (int(record_id),))
        return cur.rowcount

def export_all(db_path=DEFAULT_DB):
    return {t: fetch_records(t, db_path=db_path) for t in ("daily", "meals", "symptoms", "medications")}

def import_csv(table, uploaded_file, db_path=DEFAULT_DB):
    if table not in {"daily", "meals", "symptoms", "medications"}: raise ValueError("Unsupported table")
    frame = pd.read_csv(uploaded_file)
    required = {"daily": {"record_date"}, "meals": {"record_date", "name"},
                "symptoms": {"record_date", "main_symptom"}, "medications": {"record_date", "name"}}[table]
    if not required.issubset(frame.columns):
        raise ValueError("ไฟล์ไม่มีคอลัมน์จำเป็น: " + ", ".join(sorted(required)))
    imported, rejected = 0, []
    for idx, row in frame.iterrows():
        try:
            row = _clean(row.to_dict())
            insert_record(table, row, db_path=db_path)
            imported += 1
        except Exception as exc:
            rejected.append({"row": int(idx) + 2, "reason": str(exc)})
    return imported, rejected
