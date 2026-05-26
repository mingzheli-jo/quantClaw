from datetime import date
from app.scheduler.trading_calendar import is_trading_day


def test_weekend_is_not_trading_day():
    saturday = date(2026, 5, 23)
    sunday = date(2026, 5, 24)
    assert not is_trading_day(saturday)
    assert not is_trading_day(sunday)


def test_weekday_is_trading_day():
    monday = date(2026, 5, 25)
    assert is_trading_day(monday)


def test_known_holiday():
    national_day = date(2026, 10, 1)
    assert not is_trading_day(national_day)
