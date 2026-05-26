import pandas as pd
from app.services.strategy.scoring import (
    score_technical, score_fund, score_momentum, score_sentiment, compute_total_score,
)

def _make_bullish_kline(n=30):
    base = 20.0
    rows = []
    for i in range(n):
        c = base + i * 0.3
        rows.append({"open": c - 0.1, "high": c + 0.2, "low": c - 0.15, "close": c, "volume": 1_000_000 + i * 100_000})
    return pd.DataFrame(rows)

def _make_flat_kline(n=30):
    rows = []
    for i in range(n):
        c = 20.0 + (i % 3) * 0.1
        rows.append({"open": c, "high": c + 0.05, "low": c - 0.05, "close": c, "volume": 500_000})
    return pd.DataFrame(rows)

def test_score_technical_bullish():
    score, details = score_technical(_make_bullish_kline())
    assert 0 <= score <= 40
    assert score >= 20

def test_score_technical_flat():
    score, details = score_technical(_make_flat_kline())
    assert 0 <= score <= 40
    assert score < 20

def test_score_fund():
    fund_data = {"north_net_3d": 5_000_000, "main_net": 10_000_000, "super_large_pct": 6.0, "volume_ratio": 2.0}
    score, details = score_fund(fund_data)
    assert 0 <= score <= 30
    assert score >= 20

def test_score_fund_negative():
    fund_data = {"north_net_3d": -1_000_000, "main_net": -5_000_000, "super_large_pct": 1.0, "volume_ratio": 0.8}
    score, details = score_fund(fund_data)
    assert score <= 10

def test_score_momentum():
    momentum_data = {"pct_5d": 5.0, "relative_strength": 2.0, "is_20d_high": True}
    score, details = score_momentum(momentum_data)
    assert 0 <= score <= 20
    assert score >= 15

def test_score_sentiment():
    sentiment_data = {"sector_rank_pct": 10, "limit_up": 50, "limit_down": 10, "sector_net_flow": 100_000}
    score, details = score_sentiment(sentiment_data)
    assert 0 <= score <= 10
    assert score >= 7

def test_compute_total_score():
    weights = {"tech_weight": 0.4, "fund_weight": 0.3, "momentum_weight": 0.2, "sentiment_weight": 0.1}
    raw = {"tech": 35, "fund": 25, "momentum": 18, "sentiment": 8}
    total = compute_total_score(raw, weights)
    assert total == 86
