from unittest.mock import patch, MagicMock
from datetime import time
from app.services.data.realtime import RealtimeService


def _mock_index_response():
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "data": {
            "diff": [
                {"f12": "000001", "f14": "上证指数", "f2": 3285.62, "f3": 0.83, "f4": 27.12, "f6": 350000000000},
                {"f12": "399001", "f14": "深证成指", "f2": 10521.3, "f3": 1.12, "f4": 116.8, "f6": 480000000000},
                {"f12": "399006", "f14": "创业板指", "f2": 2103.5, "f3": 1.45, "f4": 30.05, "f6": 150000000000},
            ]
        }
    }
    resp.raise_for_status = MagicMock()
    return resp


def test_fetch_indices():
    service = RealtimeService()
    with patch("httpx.get", return_value=_mock_index_response()):
        service.refresh_indices()
    data = service.get_indices()
    assert len(data) == 3
    assert data[0]["name"] == "上证指数"
    assert data[0]["price"] == 3285.62


def test_is_trading_time():
    service = RealtimeService()
    assert service._is_trading_time(time(9, 30))
    assert service._is_trading_time(time(10, 0))
    assert service._is_trading_time(time(14, 0))
    assert not service._is_trading_time(time(12, 0))
    assert not service._is_trading_time(time(8, 0))
    assert not service._is_trading_time(time(15, 30))
