from datetime import date, datetime, timedelta

from app.clock import Clock


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
