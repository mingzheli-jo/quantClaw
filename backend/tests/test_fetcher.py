from datetime import date
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from app.services.data.fetcher import (
    fetch_stock_basic_list,
    fetch_daily_klines_batch,
    fetch_north_flow,
)


@patch("app.services.data.fetcher.ak")
def test_fetch_stock_basic_list(mock_ak):
    mock_ak.stock_zh_a_spot_em.return_value = pd.DataFrame({
        "代码": ["600000", "000001"],
        "名称": ["浦发银行", "平安银行"],
        "最新价": [10.0, 15.0],
    })
    result = fetch_stock_basic_list()
    assert len(result) >= 1
    assert "code" in result.columns
    assert "market" in result.columns
    assert "is_st" in result.columns


@patch("app.services.data.fetcher.ak")
def test_fetch_daily_klines_batch(mock_ak):
    mock_ak.stock_zh_a_hist.return_value = pd.DataFrame({
        "日期": ["2026-05-20", "2026-05-21"],
        "开盘": [10.0, 10.5],
        "最高": [10.5, 11.0],
        "最低": [9.8, 10.3],
        "收盘": [10.3, 10.8],
        "成交量": [100000, 120000],
        "成交额": [1030000, 1296000],
        "涨跌幅": [1.5, 4.85],
    })
    result = fetch_daily_klines_batch(["600000"], start_date="20260520", end_date="20260521")
    assert len(result) == 2
    assert "code" in result.columns


@patch("app.services.data.fetcher.ak")
def test_fetch_north_flow(mock_ak):
    mock_ak.stock_hsgt_north_net_flow_in_em.return_value = pd.DataFrame({
        "date": ["2026-05-20"],
        "value": [4200000000],
    })
    result = fetch_north_flow()
    assert result is not None
