from datetime import datetime, date, time, timedelta
from typing import Optional

def sleep_duration(bed_time: time | str | None, wake_time: time | str | None) -> Optional[float]:
    """Return sleep duration in hours; supports waking on the following day."""
    if bed_time in (None, "") or wake_time in (None, ""):
        return None
    if isinstance(bed_time, str):
        bed_time = time.fromisoformat(bed_time)
    if isinstance(wake_time, str):
        wake_time = time.fromisoformat(wake_time)
    start = datetime.combine(date.today(), bed_time)
    end = datetime.combine(date.today(), wake_time)
    if end <= start:
        end += timedelta(days=1)
    return round((end - start).total_seconds() / 3600, 2)

def validate_severity(value):
    if value is None or value == "":
        return None
    value = int(value)
    if not 0 <= value <= 10:
        raise ValueError("ระดับอาการต้องอยู่ระหว่าง 0–10")
    return value

def parse_iso_date(value):
    if isinstance(value, date):
        return value.isoformat()
    return date.fromisoformat(str(value)).isoformat()

def clean_optional(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value
