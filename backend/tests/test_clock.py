from datetime import date, datetime, timedelta

from httpx import ASGITransport, AsyncClient

from app.clock import Clock, get_clock
from app.config import settings
from app.main import app


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


async def test_health_uses_injected_clock():
    """前端校准源必须跟随演示偏移，否则时间偏移下前端与业务时钟错位。"""
    fixed = Clock(offset_seconds=3600)
    app.dependency_overrides[get_clock] = lambda: fixed
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/health")
    finally:
        app.dependency_overrides.pop(get_clock, None)

    assert resp.status_code == 200
    server_time = datetime.fromisoformat(resp.json()["server_time"])
    assert abs((server_time - fixed.now()).total_seconds()) < 2
