from datetime import date, datetime, timedelta

from app.clock import Clock, get_clock
from app.config import settings


def test_clock_now_is_tz_aware_asia_shanghai():
    now = Clock().now()

    assert isinstance(now, datetime)
    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(hours=8)


def test_clock_today_returns_date():
    today = Clock().today()

    assert isinstance(today, date)
    assert not isinstance(today, datetime)
    assert today == Clock().now().date()


def test_get_clock_applies_settings_offset(monkeypatch):
    """get_clock() 从 settings 读取演示偏移，-86400 秒应让「今天」早一天。"""
    monkeypatch.setattr(settings, "demo_time_offset_seconds", -86400)

    assert get_clock().today() == Clock().today() - timedelta(days=1)
