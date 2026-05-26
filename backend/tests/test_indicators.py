import pandas as pd
import numpy as np
from app.services.data.indicators import (
    calc_ma,
    calc_macd,
    calc_kdj,
    calc_rsi,
    calc_bollinger,
    calc_volume_ratio,
)


def _make_close_series(n=30, base=20.0, step=0.2):
    return pd.Series([base + i * step for i in range(n)])


def test_calc_ma():
    close = _make_close_series(20)
    ma5 = calc_ma(close, 5)
    assert len(ma5) == 20
    assert pd.isna(ma5.iloc[3])
    assert not pd.isna(ma5.iloc[4])
    expected = close.iloc[0:5].mean()
    assert abs(ma5.iloc[4] - expected) < 0.001


def test_calc_macd():
    close = _make_close_series(40)
    dif, dea, hist = calc_macd(close)
    assert len(dif) == 40
    assert len(dea) == 40
    assert len(hist) == 40


def test_calc_kdj():
    high = _make_close_series(20, base=21.0)
    low = _make_close_series(20, base=19.0)
    close = _make_close_series(20, base=20.0)
    k, d, j = calc_kdj(high, low, close)
    assert len(k) == 20
    assert all(0 <= v <= 100 for v in k.dropna())


def test_calc_rsi():
    close = _make_close_series(30)
    rsi = calc_rsi(close, 14)
    assert len(rsi) == 30
    valid = rsi.dropna()
    assert all(0 <= v <= 100 for v in valid)


def test_calc_bollinger():
    close = _make_close_series(30)
    upper, mid, lower = calc_bollinger(close, 20)
    valid_idx = mid.dropna().index
    assert all(upper[i] > mid[i] > lower[i] for i in valid_idx)


def test_calc_volume_ratio():
    volume = pd.Series([100] * 20 + [200])
    ratio = calc_volume_ratio(volume, 20)
    assert abs(ratio - 2.0) < 0.01
