from unittest.mock import patch, MagicMock
import pandas as pd
import pytest
from app.services.data.providers.base import AbstractProvider, DataSourceManager
from app.services.data.fetcher import fetch_stock_basic_list, fetch_daily_klines_batch, fetch_north_flow


class MockProvider(AbstractProvider):
    def fetch_stock_basic_list(self):
        return pd.DataFrame({
            "code": ["000001", "600000"],
            "name": ["平安银行", "浦发银行"],
            "price": [12.5, 8.3],
            "market": ["sz", "sh"],
            "is_st": [False, False],
            "list_date": [None, None],
            "industry": ["银行", "银行"],
        })

    def fetch_daily_klines(self, code, start_date, end_date):
        return pd.DataFrame({
            "code": [code], "trade_date": ["2026-05-20"],
            "open": [10.0], "high": [10.5], "low": [9.9],
            "close": [10.3], "volume": [50000000],
            "amount": [500000000.0], "change_pct": [3.0],
        })

    def fetch_north_flow(self, days=30):
        return pd.DataFrame({
            "trade_date": ["2026-05-20"],
            "buy_amount": [1e9], "sell_amount": [0], "net_amount": [1e9],
        })

    def fetch_sector_daily(self):
        return pd.DataFrame()

    def fetch_market_sentiment(self):
        return {"trade_date": "2026-05-20", "up_count": 3000, "down_count": 1500}


@pytest.fixture(autouse=True)
def setup_mock_provider():
    DataSourceManager._providers.clear()
    DataSourceManager._current = "mock"
    DataSourceManager.register("mock", MockProvider())
    yield
    DataSourceManager._providers.clear()


def test_fetch_stock_basic_list():
    df = fetch_stock_basic_list()
    assert len(df) == 2
    assert "code" in df.columns


def test_fetch_daily_klines_batch():
    df = fetch_daily_klines_batch(["000001", "600000"], "20260501", "20260520")
    assert len(df) == 2


def test_fetch_north_flow():
    df = fetch_north_flow(days=30)
    assert len(df) == 1
    assert "net_amount" in df.columns
