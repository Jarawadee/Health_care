from __future__ import annotations
from datetime import datetime, date, time, timedelta
from typing import Optional, Any
import pandas as pd

def sleep_duration_hours(bedtime: Optional[time], wake_time: Optional[time]) -> Optional[float]:
    """Return sleep duration, allowing wake-up to occur after midnight; missing/equal times are unknown."""
    if bedtime is None or wake_time is None or bedtime == wake_time:
        return None
    start = datetime.combine(date.today(), bedtime)
    end = datetime.combine(date.today(), wake_time)
    if end <= start:
        end += timedelta(days=1)
    hours = (end - start).total_seconds() / 3600
    return round(hours, 2) if 0 < hours <= 24 else None

def parse_time(value: Any) -> Optional[time]:
    if value is None or (isinstance(value, float) and pd.isna(value)) or str(value).strip() == "":
        return None
    if isinstance(value, time):
        return value
    try:
        return datetime.strptime(str(value).strip(), "%H:%M").time()
    except ValueError:
        try:
            return datetime.strptime(str(value).strip(), "%H:%M:%S").time()
        except ValueError:
            return None

def safe_mean(series: pd.Series) -> Optional[float]:
    values = pd.to_numeric(series, errors="coerce").dropna()
    return round(float(values.mean()), 2) if len(values) else None

def severity_label(value: Optional[float]) -> str:
    if value is None or pd.isna(value):
        return "ไม่ได้บันทึก"
    return f"{value:g}/10"

def time_of_day(value: Any) -> str:
    t = parse_time(value)
    if t is None:
        return "ไม่ทราบเวลา"
    h = t.hour
    if 5 <= h < 8: return "เช้ามืด"
    if 8 <= h < 12: return "ช่วงเช้า"
    if 12 <= h < 17: return "ช่วงบ่าย"
    if 17 <= h < 21: return "ช่วงเย็น"
    return "กลางคืน"

def validate_score(value: Any, field_name: str = "คะแนน") -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name}ต้องเป็นตัวเลข 0–10")
    if not 0 <= number <= 10:
        raise ValueError(f"{field_name}ต้องอยู่ระหว่าง 0–10")
    return number

def duration_minutes(start: Any, end: Any) -> Optional[int]:
    s, e = parse_time(start), parse_time(end)
    if s is None or e is None or s == e:
        return None
    start_dt = datetime.combine(date.today(), s)
    end_dt = datetime.combine(date.today(), e)
    if end_dt < start_dt:
        end_dt += timedelta(days=1)
    minutes = int((end_dt - start_dt).total_seconds() // 60)
    return minutes if 0 < minutes <= 24 * 60 else None
