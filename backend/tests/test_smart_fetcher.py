import pandas as pd
import pytest
from unittest.mock import MagicMock
from datetime import date

from app.services.data.smart_fetcher import SmartFetcher


@pytest.fixture
def fetcher():
    primary = MagicMock()
    fallback = MagicMock()
    return SmartFetcher(primary=primary, fallback=fallback), primary, fallback


def test_stock_list_uses_primary(fetcher):
    sf, primary, fallback = fetcher
    primary.fetch_stock_basic_list.return_value = pd.DataFrame([{"code": "000001"}])
    result = sf.fetch_stock_basic_list()
    assert len(result) == 1
    primary.fetch_stock_basic_list.assert_called_once()
    fallback.fetch_stock_basic_list.assert_not_called()


def test_stock_list_falls_back(fetcher):
    sf, primary, fallback = fetcher
    primary.fetch_stock_basic_list.side_effect = Exception("banned")
    fallback.fetch_stock_basic_list.return_value = pd.DataFrame([{"code": "000001"}])
    result = sf.fetch_stock_basic_list()
    assert len(result) == 1
    fallback.fetch_stock_basic_list.assert_called_once()


def test_stock_list_falls_back_on_empty(fetcher):
    sf, primary, fallback = fetcher
    primary.fetch_stock_basic_list.return_value = pd.DataFrame()
    fallback.fetch_stock_basic_list.return_value = pd.DataFrame([{"code": "000001"}])
    result = sf.fetch_stock_basic_list()
    assert len(result) == 1


def test_north_flow_no_fallback(fetcher):
    sf, primary, fallback = fetcher
    primary.fetch_north_flow.side_effect = Exception("banned")
    result = sf.fetch_north_flow(days=5)
    assert result.empty
    fallback.fetch_north_flow.assert_not_called()


def test_sentiment_uses_primary(fetcher):
    sf, primary, fallback = fetcher
    primary.fetch_market_sentiment.return_value = {"trade_date": date.today(), "up_count": 2000}
    result = sf.fetch_market_sentiment()
    assert result["up_count"] == 2000
