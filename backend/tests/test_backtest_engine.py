import pandas as pd
from datetime import date
from app.services.backtest.engine import BacktestEngine


def _make_klines(code: str, days: int, base_price: float = 10.0):
    records = []
    d = date(2026, 1, 5)
    for i in range(days):
        while d.weekday() >= 5:
            d = date.fromordinal(d.toordinal() + 1)
        price = base_price + i * 0.1
        records.append({
            "code": code, "trade_date": d,
            "open": price, "high": price + 0.2, "low": price - 0.1,
            "close": price, "volume": 50_000_000, "amount": price * 50_000_000,
            "change_pct": 1.0,
        })
        d = date.fromordinal(d.toordinal() + 1)
    return records


def test_engine_runs_and_returns_result():
    klines = _make_klines("000001", 60) + _make_klines("600000", 60)
    kline_df = pd.DataFrame(klines)
    stocks_df = pd.DataFrame([
        {"code": "000001", "name": "Test A", "market": "sz", "is_st": False, "list_date": date(2020, 1, 1), "industry": "银行"},
        {"code": "600000", "name": "Test B", "market": "sh", "is_st": False, "list_date": date(2020, 1, 1), "industry": "银行"},
    ])
    strategy_config = {
        "filter_config": {"min_amount_20d": 1, "max_price": 9999, "min_list_days": 1, "exclude_bj": True},
        "score_config": {"tech_weight": 0.4, "fund_weight": 0.3, "momentum_weight": 0.2, "sentiment_weight": 0.1},
        "signal_config": {"min_score": 0, "top_n": 2, "concentration_control": False},
        "risk_config": {"stop_loss_pct": -0.05, "take_profit_pct": 0.12, "max_hold_days": 5, "trailing_trigger": 0.07, "trailing_drawdown": 0.03},
    }
    engine = BacktestEngine(
        stocks_df=stocks_df, kline_df=kline_df,
        strategy_config=strategy_config,
        start_date=date(2026, 2, 2), end_date=date(2026, 3, 20),
        initial_capital=50000,
    )
    result = engine.run()
    assert "total_return" in result["summary"]
    assert "max_drawdown" in result["summary"]
    assert "win_rate" in result["summary"]
    assert len(result["daily_values"]) > 0
    assert isinstance(result["trades"], list)


def test_engine_stop_loss():
    records = []
    d = date(2026, 2, 2)
    for i in range(30):
        while d.weekday() >= 5:
            d = date.fromordinal(d.toordinal() + 1)
        price = 10.0 - i * 0.3 if i > 0 else 10.0
        records.append({
            "code": "000001", "trade_date": d,
            "open": price, "high": price + 0.1, "low": price - 0.1,
            "close": max(price, 1.0), "volume": 50_000_000, "amount": 500_000_000,
            "change_pct": -3.0,
        })
        d = date.fromordinal(d.toordinal() + 1)
    kline_df = pd.DataFrame(records)
    stocks_df = pd.DataFrame([
        {"code": "000001", "name": "Loser", "market": "sz", "is_st": False, "list_date": date(2020, 1, 1), "industry": "银行"},
    ])
    config = {
        "filter_config": {"min_amount_20d": 1, "max_price": 9999, "min_list_days": 1, "exclude_bj": True},
        "score_config": {"tech_weight": 0.25, "fund_weight": 0.25, "momentum_weight": 0.25, "sentiment_weight": 0.25},
        "signal_config": {"min_score": 0, "top_n": 1, "concentration_control": False},
        "risk_config": {"stop_loss_pct": -0.05, "take_profit_pct": 0.50, "max_hold_days": 30, "trailing_trigger": 0.5, "trailing_drawdown": 0.3},
    }
    engine = BacktestEngine(
        stocks_df=stocks_df, kline_df=kline_df,
        strategy_config=config,
        start_date=date(2026, 2, 2), end_date=date(2026, 3, 15),
        initial_capital=50000,
    )
    result = engine.run()
    assert result["summary"]["total_return"] < 0
    sells_with_stop = [t for t in result["trades"] if t.get("sell_reason") == "stop_loss"]
    assert len(sells_with_stop) > 0
