from datetime import date, timedelta
import pandas as pd
from app.services.strategy.filters import hard_filter

DEFAULT_CONFIG = {
    "min_amount_20d": 50_000_000,
    "max_price": 50,
    "min_list_days": 60,
}

def _make_stock_df():
    today = date.today()
    return pd.DataFrame([
        {"code": "600001", "name": "正常股票", "close": 25.0, "avg_amount_20d": 80_000_000,
         "list_date": today - timedelta(days=100), "market": "sh", "is_st": False,
         "is_suspended": False, "is_limit_up": False, "is_limit_down": False},
        {"code": "600002", "name": "ST股票", "close": 5.0, "avg_amount_20d": 60_000_000,
         "list_date": today - timedelta(days=200), "market": "sh", "is_st": True,
         "is_suspended": False, "is_limit_up": False, "is_limit_down": False},
        {"code": "600003", "name": "高价股", "close": 80.0, "avg_amount_20d": 100_000_000,
         "list_date": today - timedelta(days=200), "market": "sh", "is_st": False,
         "is_suspended": False, "is_limit_up": False, "is_limit_down": False},
        {"code": "600004", "name": "低流动性", "close": 10.0, "avg_amount_20d": 30_000_000,
         "list_date": today - timedelta(days=200), "market": "sh", "is_st": False,
         "is_suspended": False, "is_limit_up": False, "is_limit_down": False},
        {"code": "600005", "name": "新上市", "close": 15.0, "avg_amount_20d": 80_000_000,
         "list_date": today - timedelta(days=30), "market": "sh", "is_st": False,
         "is_suspended": False, "is_limit_up": False, "is_limit_down": False},
        {"code": "830001", "name": "北交所", "close": 12.0, "avg_amount_20d": 80_000_000,
         "list_date": today - timedelta(days=200), "market": "bj", "is_st": False,
         "is_suspended": False, "is_limit_up": False, "is_limit_down": False},
        {"code": "600006", "name": "涨停股", "close": 30.0, "avg_amount_20d": 90_000_000,
         "list_date": today - timedelta(days=200), "market": "sh", "is_st": False,
         "is_suspended": False, "is_limit_up": True, "is_limit_down": False},
        {"code": "600007", "name": "又一正常", "close": 18.0, "avg_amount_20d": 70_000_000,
         "list_date": today - timedelta(days=300), "market": "sz", "is_st": False,
         "is_suspended": False, "is_limit_up": False, "is_limit_down": False},
    ])

def test_hard_filter_removes_st():
    result = hard_filter(_make_stock_df(), DEFAULT_CONFIG)
    assert "600002" not in result["code"].values

def test_hard_filter_removes_high_price():
    result = hard_filter(_make_stock_df(), DEFAULT_CONFIG)
    assert "600003" not in result["code"].values

def test_hard_filter_removes_low_liquidity():
    result = hard_filter(_make_stock_df(), DEFAULT_CONFIG)
    assert "600004" not in result["code"].values

def test_hard_filter_removes_new_listing():
    result = hard_filter(_make_stock_df(), DEFAULT_CONFIG)
    assert "600005" not in result["code"].values

def test_hard_filter_removes_bj():
    result = hard_filter(_make_stock_df(), DEFAULT_CONFIG)
    assert "830001" not in result["code"].values

def test_hard_filter_removes_limit_up():
    result = hard_filter(_make_stock_df(), DEFAULT_CONFIG)
    assert "600006" not in result["code"].values

def test_hard_filter_keeps_valid():
    result = hard_filter(_make_stock_df(), DEFAULT_CONFIG)
    assert "600001" in result["code"].values
    assert "600007" in result["code"].values
    assert len(result) == 2
