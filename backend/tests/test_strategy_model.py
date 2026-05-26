from app.models.strategy import StrategyTemplate, BacktestResult


def test_strategy_template_fields():
    t = StrategyTemplate(
        name="test", description="test strategy",
        filter_config={"min_amount_20d": 50000000},
        score_config={"tech_weight": 0.4},
        signal_config={"min_score": 65},
        risk_config={"stop_loss_pct": -0.05},
        is_active=True, is_builtin=False,
    )
    assert t.name == "test"
    assert t.is_active is True
    assert t.filter_config["min_amount_20d"] == 50000000


def test_backtest_result_fields():
    r = BacktestResult(
        strategy_id=1, strategy_name="test",
        start_date="2025-09-01", end_date="2026-05-26",
        initial_capital=50000, status="running",
    )
    assert r.status == "running"
    assert r.initial_capital == 50000
