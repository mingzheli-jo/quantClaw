from datetime import date
from app.scheduler.trading_calendar import is_trading_day


def test_weekday_is_trading_day():
    assert is_trading_day(date(2026, 5, 25)) is True


def test_weekend_is_not_trading_day():
    assert is_trading_day(date(2026, 5, 23)) is False
    assert is_trading_day(date(2026, 5, 24)) is False
