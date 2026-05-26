from unittest.mock import patch, MagicMock
import pandas as pd
import pytest
from app.services.data.providers.eastmoney import EastmoneyProvider


@pytest.fixture
def provider():
    return EastmoneyProvider()


def _mock_response(data):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = data
    resp.raise_for_status = MagicMock()
    return resp


class TestFetchStockBasicList:
    def test_parses_eastmoney_response(self, provider):
        mock_data = {
            "data": {
                "diff": [
                    {"f12": "000001", "f14": "平安银行", "f2": 12.5, "f3": 1.2, "f100": "银行"},
                    {"f12": "600000", "f14": "浦发银行", "f2": 8.3, "f3": -0.5, "f100": "银行"},
                ]
            }
        }
        with patch("httpx.get", return_value=_mock_response(mock_data)):
            df = provider.fetch_stock_basic_list()
        assert len(df) == 2
        assert "code" in df.columns
        assert df.iloc[0]["code"] == "000001"
        assert df.iloc[0]["market"] == "sz"
        assert df.iloc[1]["market"] == "sh"

    def test_returns_empty_on_failure(self, provider):
        with patch("httpx.get", side_effect=Exception("timeout")):
            df = provider.fetch_stock_basic_list()
        assert df.empty


class TestFetchDailyKlines:
    def test_parses_kline_response(self, provider):
        mock_data = {
            "data": {
                "klines": [
                    "2026-05-20,10.00,10.30,10.50,9.90,50000000,500000000.00,3.00",
                    "2026-05-21,10.30,10.60,10.80,10.20,60000000,600000000.00,2.91",
                ]
            }
        }
        with patch("httpx.get", return_value=_mock_response(mock_data)):
            df = provider.fetch_daily_klines("000001", "20260520", "20260521")
        assert len(df) == 2
        assert df.iloc[0]["close"] == 10.30
        assert df.iloc[0]["code"] == "000001"
