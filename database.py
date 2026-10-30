from pathlib import Path
import sqlite3
import json
import csv
import io
from contextlib import contextmanager
from datetime import date
from utils import parse_iso_date, validate_severity, clean_optional

DEFAULT_DB = Path(__file__).resolve().parent / "data" / "health_diary.db"

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS daily_entries (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 entry_date TEXT NOT NULL UNIQUE,
 entry_time TEXT,
 daily_note TEXT,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS sleep_records (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 entry_id INTEGER NOT NULL UNIQUE REFERENCES daily_entries(id) ON DELETE CASCADE,
 bed_time TEXT, wake_time TEXT, duration_hours REAL, quality INTEGER,
 awakenings INTEGER, note TEXT,
 CHECK(quality IS NULL OR quality BETWEEN 1 AND 5),
 CHECK(awakenings IS NULL OR awakenings >= 0)
);
CREATE TABLE IF NOT EXISTS vertigo_symptoms (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 entry_id INTEGER NOT NULL UNIQUE REFERENCES daily_entries(id) ON DELETE CASCADE,
 has_symptom INTEGER NOT NULL DEFAULT 0, start_time TEXT, duration_minutes REAL,
 severity INTEGER, symptom_type TEXT, activity TEXT, associated_symptoms TEXT,
 suspected_factors TEXT, note TEXT,
 CHECK(severity IS NULL OR severity BETWEEN 0 AND 10)
);
CREATE TABLE IF NOT EXISTS headache_symptoms (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 entry_id INTEGER NOT NULL UNIQUE REFERENCES daily_entries(id) ON DELETE CASCADE,
 has_symptom INTEGER NOT NULL DEFAULT 0, severity INTEGER, location TEXT,
 pain_type TEXT, duration_minutes REAL, associated_symptoms TEXT, note TEXT,
 CHECK(severity IS NULL OR severity BETWEEN 0 AND 10)
);
CREATE TABLE IF NOT EXISTS meals (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 entry_id INTEGER NOT NULL REFERENCES daily_entries(id) ON DELETE CASCADE,
 meal_time TEXT, meal_type TEXT, item TEXT NOT NULL, amount TEXT,
 caffeine TEXT, alcohol TEXT, water_ml REAL, note TEXT
);
CREATE TABLE IF NOT EXISTS medications (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 entry_id INTEGER NOT NULL REFERENCES daily_entries(id) ON DELETE CASCADE,
 name TEXT NOT NULL, dose TEXT, taken_at TEXT, purpose TEXT,
 observed_effect TEXT, adverse_effect TEXT, note TEXT
);
CREATE TABLE IF NOT EXISTS lifestyle_factors (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 entry_id INTEGER NOT NULL UNIQUE REFERENCES daily_entries(id) ON DELETE CASCADE,
 stress INTEGER, fatigue INTEGER, exercise TEXT, screen_hours REAL,
 water_ml REAL, routine_change TEXT, note TEXT,
 CHECK(stress IS NULL OR stress BETWEEN 0 AND 10),
 CHECK(fatigue IS NULL OR fatigue BETWEEN 0 AND 10)
);
"""

@contextmanager
def connect(db_path=DEFAULT_DB):
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db(db_path=DEFAULT_DB):
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)

def _upsert(conn, table, entry_id, values):
    cols = ["entry_id"] + list(values)
    vals = [entry_id] + list(values.values())
    placeholders = ",".join("?" for _ in cols)
    updates = ",".join(f"{c}=excluded.{c}" for c in values)
    conn.execute(
        f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders}) "
        f"ON CONFLICT(entry_id) DO UPDATE SET {updates}", vals
    )

def save_daily(payload, db_path=DEFAULT_DB):
    entry_date = parse_iso_date(payload["entry_date"])
    with connect(db_path) as conn:
        conn.execute(
            """INSERT INTO daily_entries(entry_date,entry_time,daily_note)
               VALUES(?,?,?) ON CONFLICT(entry_date) DO UPDATE SET
               entry_time=excluded.entry_time,daily_note=excluded.daily_note,
               updated_at=CURRENT_TIMESTAMP""",
            (entry_date, clean_optional(payload.get("entry_time")), clean_optional(payload.get("daily_note")))
        )
        entry_id = conn.execute("SELECT id FROM daily_entries WHERE entry_date=?", (entry_date,)).fetchone()["id"]
        for table, key in [
            ("sleep_records","sleep"), ("vertigo_symptoms","vertigo"),
            ("headache_symptoms","headache"), ("lifestyle_factors","lifestyle")
        ]:
            values = payload.get(key, {})
            if values:
                _upsert(conn, table, entry_id, values)
        return entry_id

def add_meal(entry_id, item, db_path=DEFAULT_DB):
    with connect(db_path) as conn:
        cur = conn.execute("""INSERT INTO meals(entry_id,meal_time,meal_type,item,amount,caffeine,
            alcohol,water_ml,note) VALUES(?,?,?,?,?,?,?,?,?)""",
            (entry_id,item.get("meal_time"),item.get("meal_type"),item["item"],item.get("amount"),
             item.get("caffeine"),item.get("alcohol"),item.get("water_ml"),item.get("note")))
        return cur.lastrowid

def add_medication(entry_id, item, db_path=DEFAULT_DB):
    with connect(db_path) as conn:
        cur = conn.execute("""INSERT INTO medications(entry_id,name,dose,taken_at,purpose,
            observed_effect,adverse_effect,note) VALUES(?,?,?,?,?,?,?,?)""",
            (entry_id,item["name"],item.get("dose"),item.get("taken_at"),item.get("purpose"),
             item.get("observed_effect"),item.get("adverse_effect"),item.get("note")))
        return cur.lastrowid

def delete_child(table, item_id, db_path=DEFAULT_DB):
    if table not in {"meals", "medications"}:
        raise ValueError("Unsupported record type")
    with connect(db_path) as conn:
        cur = conn.execute(f"DELETE FROM {table} WHERE id=?", (int(item_id),))
        return cur.rowcount > 0

def get_day(entry_date, db_path=DEFAULT_DB):
    d = parse_iso_date(entry_date)
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM daily_entries WHERE entry_date=?", (d,)).fetchone()
        if not row:
            return None
        result = dict(row)
        eid = row["id"]
        for key, table in [("sleep","sleep_records"),("vertigo","vertigo_symptoms"),
                           ("headache","headache_symptoms"),("lifestyle","lifestyle_factors")]:
            r = conn.execute(f"SELECT * FROM {table} WHERE entry_id=?", (eid,)).fetchone()
            result[key] = dict(r) if r else {}
        result["meals"] = [dict(r) for r in conn.execute("SELECT * FROM meals WHERE entry_id=? ORDER BY meal_time,id",(eid,))]
        result["medications"] = [dict(r) for r in conn.execute("SELECT * FROM medications WHERE entry_id=? ORDER BY taken_at,id",(eid,))]
        return result

def list_days(start=None, end=None, db_path=DEFAULT_DB):
    clauses, args = [], []
    if start: clauses.append("entry_date>=?"); args.append(parse_iso_date(start))
    if end: clauses.append("entry_date<=?"); args.append(parse_iso_date(end))
    sql = "SELECT * FROM daily_entries" + (" WHERE " + " AND ".join(clauses) if clauses else "") + " ORDER BY entry_date DESC"
    with connect(db_path) as conn:
        return [dict(r) for r in conn.execute(sql,args)]

def list_history(start=None, end=None, db_path=DEFAULT_DB):
    days = list_days(start,end,db_path)
    return [get_day(x["entry_date"],db_path) for x in days]

def delete_day(entry_date, db_path=DEFAULT_DB):
    with connect(db_path) as conn:
        cur = conn.execute("DELETE FROM daily_entries WHERE entry_date=?", (parse_iso_date(entry_date),))
        return cur.rowcount > 0

def get_entry_id(entry_date, db_path=DEFAULT_DB):
    with connect(db_path) as conn:
        r=conn.execute("SELECT id FROM daily_entries WHERE entry_date=?",(parse_iso_date(entry_date),)).fetchone()
        return r["id"] if r else None

def export_json(db_path=DEFAULT_DB):
    data = list_history(db_path=db_path)
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)

def export_csv(db_path=DEFAULT_DB):
    output=io.StringIO()
    fields=["entry_date","daily_note","sleep_duration_hours","sleep_quality","vertigo_present",
            "vertigo_severity","headache_present","headache_severity","stress","fatigue",
            "meal_count","medication_count"]
    writer=csv.DictWriter(output,fieldnames=fields)
    writer.writeheader()
    for d in list_history(db_path=db_path):
        writer.writerow({
            "entry_date":d["entry_date"],"daily_note":d.get("daily_note"),
            "sleep_duration_hours":d["sleep"].get("duration_hours"),"sleep_quality":d["sleep"].get("quality"),
            "vertigo_present":d["vertigo"].get("has_symptom"),"vertigo_severity":d["vertigo"].get("severity"),
            "headache_present":d["headache"].get("has_symptom"),"headache_severity":d["headache"].get("severity"),
            "stress":d["lifestyle"].get("stress"),"fatigue":d["lifestyle"].get("fatigue"),
            "meal_count":len(d["meals"]),"medication_count":len(d["medications"])
        })
    return output.getvalue()

def import_json(raw, db_path=DEFAULT_DB):
    data=json.loads(raw)
    if not isinstance(data,list):
        raise ValueError("ไฟล์ JSON ต้องเป็นรายการข้อมูล (list)")
    dates=[]
    for d in data:
        if not isinstance(d,dict) or "entry_date" not in d:
            raise ValueError("รูปแบบข้อมูลไม่ถูกต้อง: ต้องมี entry_date")
        dates.append(parse_iso_date(d["entry_date"]))
    if len(dates) != len(set(dates)):
        raise ValueError("ไฟล์นำเข้ามีวันที่ซ้ำกัน กรุณาตรวจสอบก่อนนำเข้า")
    for d, day in zip(data, dates):
        if get_day(day,db_path) is not None:
            raise ValueError(f"วันที่ {day} มีข้อมูลอยู่แล้ว กรุณาสำรองและจัดการข้อมูลซ้ำก่อนนำเข้า")
    imported=0
    for d in data:
        payload={k:d[k] for k in ("entry_date","entry_time","daily_note","sleep","vertigo","headache","lifestyle") if k in d}
        eid=save_daily(payload,db_path)
        for m in d.get("meals",[]): add_meal(eid,m,db_path)
        for m in d.get("medications",[]): add_medication(eid,m,db_path)
        imported+=1
    return imported
