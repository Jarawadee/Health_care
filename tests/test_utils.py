from datetime import time
import pytest
from utils import sleep_duration_hours, duration_minutes, validate_score, time_of_day

def test_sleep_crosses_midnight():
    assert sleep_duration_hours(time(23, 0), time(7, 0)) == 8.0

def test_sleep_missing_or_equal():
    assert sleep_duration_hours(None, time(7, 0)) is None
    assert sleep_duration_hours(time(7, 0), time(7, 0)) is None

def test_duration_crosses_midnight():
    assert duration_minutes("23:30", "00:15") == 45

def test_validate_score():
    assert validate_score(5) == 5.0
    with pytest.raises(ValueError):
        validate_score(11)

def test_time_of_day():
    assert time_of_day("09:30") == "ช่วงเช้า"
    assert time_of_day(None) == "ไม่ทราบเวลา"
