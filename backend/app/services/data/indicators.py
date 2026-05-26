import pandas as pd
import numpy as np


def calc_ma(close: pd.Series, period: int) -> pd.Series:
    return close.rolling(window=period).mean()


def calc_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    hist = 2 * (dif - dea)
    return dif, dea, hist


def calc_kdj(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 9):
    lowest = low.rolling(window=period).min()
    highest = high.rolling(window=period).max()
    rsv = (close - lowest) / (highest - lowest) * 100
    rsv = rsv.fillna(50)
    k = rsv.ewm(com=2, adjust=False).mean()
    d = k.ewm(com=2, adjust=False).mean()
    j = 3 * k - 2 * d
    k = k.clip(0, 100)
    d = d.clip(0, 100)
    return k, d, j


def calc_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(span=period, adjust=False).mean()
    avg_loss = loss.ewm(span=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calc_bollinger(close: pd.Series, period: int = 20, num_std: float = 2.0):
    mid = close.rolling(window=period).mean()
    std = close.rolling(window=period).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    return upper, mid, lower


def calc_volume_ratio(volume: pd.Series, period: int = 20) -> float:
    if len(volume) < period + 1:
        return 1.0
    avg = volume.iloc[-(period + 1):-1].mean()
    if avg == 0:
        return 1.0
    return volume.iloc[-1] / avg
