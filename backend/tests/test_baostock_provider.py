from unittest.mock import patch, MagicMock
import pandas as pd
import pytest
from app.services.data.providers.baostock_provider import BaostockProvider


@pytest.fixture
def provider():
    return BaostockProvider()


def test_fetch_stock_basic_list(provider):
    result_df = pd.DataFrame({
        "code": ["sh.600000", "sz.000001"],
        "code_name": ["浦发银行", "平安银行"],
        "ipoDate": ["1999-11-10", "1991-04-03"],
        "industry": ["银行", "银行"],
        "type": ["1", "1"],
        "status": ["1", "1"],
    })
    with patch.object(provider, "_query_stock_list", return_value=result_df):
        df = provider.fetch_stock_basic_list()
    assert len(df) == 2
    assert "code" in df.columns
    assert df.iloc[0]["code"] == "600000"
    assert df.iloc[0]["market"] == "sh"
    assert df.iloc[1]["code"] == "000001"
    assert df.iloc[1]["market"] == "sz"


def test_north_flow_returns_empty(provider):
    df = provider.fetch_north_flow()
    assert df.empty


def test_sector_daily_returns_empty(provider):
    df = provider.fetch_sector_daily()
    assert df.empty


def test_market_sentiment_returns_dict(provider):
    mock_df = pd.DataFrame([
        {"code": "000001", "change_pct": 5.0},
        {"code": "000002", "change_pct": -3.0},
    ])
    with patch.object(provider, "_fetch_klines_for_sentiment", return_value=mock_df):
        result = provider.fetch_market_sentiment()
    assert isinstance(result, dict)
    assert result["up_count"] == 1
    assert result["down_count"] == 1
