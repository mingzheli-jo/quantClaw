import pandas as pd
import numpy as np
from app.services.data.indicators import calc_ma, calc_macd, calc_kdj, calc_rsi, calc_bollinger, calc_volume_ratio


def score_technical(kline_df: pd.DataFrame) -> tuple[int, dict]:
    score = 0
    details = {}
    close = kline_df["close"]
    high = kline_df["high"]
    low = kline_df["low"]
    volume = kline_df["volume"]

    ma5 = calc_ma(close, 5)
    ma10 = calc_ma(close, 10)
    ma20 = calc_ma(close, 20)
    if len(close) >= 20:
        last_ma5, last_ma10, last_ma20 = ma5.iloc[-1], ma10.iloc[-1], ma20.iloc[-1]
        if not any(pd.isna([last_ma5, last_ma10, last_ma20])):
            min_spread = last_ma20 * 0.002  # require 0.2% relative spread to avoid noise
            if last_ma5 > last_ma10 + min_spread and last_ma10 > last_ma20 + min_spread:
                score += 10
                details["ma_alignment"] = "bullish"
            elif last_ma5 > last_ma10 + min_spread:
                score += 5
                details["ma_alignment"] = "partial"
            else:
                details["ma_alignment"] = "bearish"

    if len(close) >= 26:
        dif, dea, hist = calc_macd(close)
        min_hist = close.iloc[-1] * 0.001  # require 0.1% of price as minimum histogram magnitude
        if hist.iloc[-1] > min_hist and hist.iloc[-2] <= 0:
            score += 8
            details["macd"] = "golden_cross"
        elif hist.iloc[-1] > min_hist:
            score += 4
            details["macd"] = "positive"
        else:
            details["macd"] = "negative"

    if len(close) >= 20:
        upper, mid, lower = calc_bollinger(close, 20)
        if not pd.isna(mid.iloc[-1]):
            if close.iloc[-1] > mid.iloc[-1]:
                score += 7 if close.iloc[-1] < upper.iloc[-1] else 4
                details["bollinger"] = "above_mid"
            else:
                details["bollinger"] = "below_mid"

    if len(close) >= 9:
        k, d, j = calc_kdj(high, low, close)
        if 20 < k.iloc[-1] < 80 and k.iloc[-1] > d.iloc[-1] and k.iloc[-2] <= d.iloc[-2]:
            score += 5
            details["kdj"] = "golden_cross"
        elif 20 < k.iloc[-1] < 80 and k.iloc[-1] > d.iloc[-1]:
            score += 2
            details["kdj"] = "bullish_zone"
        else:
            details["kdj"] = "neutral"

    vol_ratio = calc_volume_ratio(volume, 20) if len(volume) >= 21 else 1.0
    if vol_ratio >= 1.5:
        score += 5
        details["volume"] = f"ratio_{vol_ratio:.1f}"
    elif vol_ratio >= 1.2:
        score += 2
        details["volume"] = f"ratio_{vol_ratio:.1f}"
    else:
        details["volume"] = f"ratio_{vol_ratio:.1f}"

    if len(close) >= 20:
        high_20d = close.iloc[-20:].max()
        if close.iloc[-1] >= high_20d:
            score += 5
            details["breakout"] = "20d_high"
        else:
            details["breakout"] = "no"

    return min(score, 40), details


def score_fund(fund_data: dict) -> tuple[int, dict]:
    score = 0
    details = {}
    if fund_data.get("north_net_3d", 0) > 0:
        score += 10
        details["north"] = "positive"
    else:
        details["north"] = "negative"
    if fund_data.get("main_net", 0) > 0:
        score += 10
        details["main_fund"] = "inflow"
    else:
        details["main_fund"] = "outflow"
    if fund_data.get("super_large_pct", 0) > 5:
        score += 5
        details["super_large"] = f"{fund_data['super_large_pct']:.1f}%"
    else:
        details["super_large"] = f"{fund_data.get('super_large_pct', 0):.1f}%"
    vr = fund_data.get("volume_ratio", 1.0)
    if 1.5 <= vr < 5:
        score += 5
        details["volume_ratio"] = f"{vr:.1f}"
    else:
        details["volume_ratio"] = f"{vr:.1f}"
    return min(score, 30), details


def score_momentum(momentum_data: dict) -> tuple[int, dict]:
    score = 0
    details = {}
    pct_5d = momentum_data.get("pct_5d", 0)
    if 3 <= pct_5d <= 10:
        score += 8
        details["5d_pct"] = f"{pct_5d:.1f}%"
    elif 0 < pct_5d < 3:
        score += 4
        details["5d_pct"] = f"{pct_5d:.1f}%"
    else:
        details["5d_pct"] = f"{pct_5d:.1f}%"
    if momentum_data.get("relative_strength", 0) > 0:
        score += 7
        details["rel_strength"] = "outperform"
    else:
        details["rel_strength"] = "underperform"
    if momentum_data.get("is_20d_high", False):
        score += 5
        details["20d_high"] = True
    return min(score, 20), details


def score_sentiment(sentiment_data: dict) -> tuple[int, dict]:
    score = 0
    details = {}
    rank_pct = sentiment_data.get("sector_rank_pct", 50)
    if rank_pct <= 20:
        score += 5
        details["sector_rank"] = f"top_{rank_pct}%"
    else:
        details["sector_rank"] = f"top_{rank_pct}%"
    lu = sentiment_data.get("limit_up", 0)
    ld = sentiment_data.get("limit_down", 0)
    if lu > ld * 2 and ld > 0:
        score += 3
        details["market_mood"] = "bullish"
    elif lu > ld:
        score += 1
        details["market_mood"] = "neutral"
    else:
        details["market_mood"] = "bearish"
    if sentiment_data.get("sector_net_flow", 0) > 0:
        score += 2
        details["sector_flow"] = "inflow"
    else:
        details["sector_flow"] = "outflow"
    return min(score, 10), details


def compute_total_score(raw_scores: dict, weights: dict | None = None) -> int:
    if weights is None:
        return raw_scores["tech"] + raw_scores["fund"] + raw_scores["momentum"] + raw_scores["sentiment"]
    max_scores = {"tech": 40, "fund": 30, "momentum": 20, "sentiment": 10}
    total = 0.0
    for key in ["tech", "fund", "momentum", "sentiment"]:
        w = weights.get(f"{key}_weight", 0.25)
        normalized = raw_scores[key] / max_scores[key] if max_scores[key] > 0 else 0
        total += normalized * w
    return int(round(total * 100))
