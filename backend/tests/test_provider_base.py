from unittest.mock import patch, MagicMock
import pandas as pd
from app.services.data.providers.base import AbstractProvider, DataSourceManager


class FakeProvider(AbstractProvider):
    def fetch_stock_basic_list(self):
        return pd.DataFrame({"code": ["000001"], "name": ["Test"]})

    def fetch_daily_klines(self, code, start_date, end_date):
        return pd.DataFrame()

    def fetch_north_flow(self, days=30):
        return pd.DataFrame()

    def fetch_sector_daily(self):
        return pd.DataFrame()

    def fetch_market_sentiment(self):
        return {}


def test_register_and_get_provider():
    DataSourceManager._providers.clear()
    DataSourceManager._current = "fake"
    fake = FakeProvider()
    DataSourceManager.register("fake", fake)
    assert DataSourceManager.get_provider() is fake
    assert "fake" in DataSourceManager.available_sources()


def test_get_provider_fallback():
    DataSourceManager._providers.clear()
    DataSourceManager._current = "nonexistent"
    fake = FakeProvider()
    DataSourceManager.register("eastmoney", fake)
    provider = DataSourceManager.get_provider()
    assert provider is fake
