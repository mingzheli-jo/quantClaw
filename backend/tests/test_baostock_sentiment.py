from datetime import date
from unittest.mock import patch
import pandas as pd

from app.services.data.providers.baostock_provider import BaostockProvider


def test_fetch_market_sentiment_calculates_from_klines():
    provider = BaostockProvider()
    mock_df = pd.DataFrame([
        {"code": "000001", "change_pct": 5.0},
        {"code": "000002", "change_pct": -3.0},
        {"code": "000003", "change_pct": 0.0},
        {"code": "000004", "change_pct": 10.0},
        {"code": "000005", "change_pct": -10.0},
    ])
    with patch.object(provider, "_fetch_klines_for_sentiment", return_value=mock_df):
        result = provider.fetch_market_sentiment()
    assert result["up_count"] == 2
    assert result["down_count"] == 2
    assert result["flat_count"] == 1
    assert result["limit_up"] == 1
    assert result["limit_down"] == 1
    assert result["trade_date"] == date.today()


def test_fetch_market_sentiment_empty():
    provider = BaostockProvider()
    with patch.object(provider, "_fetch_klines_for_sentiment", return_value=pd.DataFrame()):
        result = provider.fetch_market_sentiment()
    assert result == {}
