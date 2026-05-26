import logging
from datetime import date

import akshare as ak
import pandas as pd

logger = logging.getLogger(__name__)
_HOLIDAY_CACHE: set[date] | None = None


def _load_holidays() -> set[date]:
    global _HOLIDAY_CACHE
    if _HOLIDAY_CACHE is not None:
        return _HOLIDAY_CACHE
    try:
        df = ak.tool_trade_date_hist_sina()
        all_trade_dates = set(pd.to_datetime(df["trade_date"]).dt.date)
        year = date.today().year
        all_dates_this_year = set(pd.bdate_range(start=f"{year}-01-01", end=f"{year}-12-31").date)
        _HOLIDAY_CACHE = all_dates_this_year - all_trade_dates
    except Exception as e:
        logger.warning(f"Failed to load holiday calendar: {e}, falling back to weekday-only")
        _HOLIDAY_CACHE = set()
    return _HOLIDAY_CACHE


def is_trading_day(d: date | None = None) -> bool:
    if d is None:
        d = date.today()
    if d.weekday() >= 5:
        return False
    holidays = _load_holidays()
    return d not in holidays
