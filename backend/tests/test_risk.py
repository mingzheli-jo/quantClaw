from app.services.position.risk import check_sell_signals, RiskConfig


def _make_position(buy_price=20.0, highest_price=20.0, hold_days=1):
    return {"buy_price": buy_price, "highest_price": highest_price, "hold_days": hold_days, "current_price": None}


def test_stop_loss_triggers():
    pos = _make_position(buy_price=20.0)
    pos["current_price"] = 18.9
    signals = check_sell_signals(pos, RiskConfig())
    assert any(s["rule"] == "stop_loss" for s in signals)


def test_stop_loss_not_triggered():
    pos = _make_position(buy_price=20.0)
    pos["current_price"] = 19.5
    signals = check_sell_signals(pos, RiskConfig())
    assert not any(s["rule"] == "stop_loss" for s in signals)


def test_trailing_stop_triggers():
    pos = _make_position(buy_price=20.0, highest_price=22.0)
    pos["current_price"] = 21.3
    signals = check_sell_signals(pos, RiskConfig())
    assert any(s["rule"] == "trailing_stop" for s in signals)


def test_trailing_stop_not_yet():
    pos = _make_position(buy_price=20.0, highest_price=21.0)
    pos["current_price"] = 20.5
    signals = check_sell_signals(pos, RiskConfig())
    assert not any(s["rule"] == "trailing_stop" for s in signals)


def test_fixed_take_profit():
    pos = _make_position(buy_price=20.0)
    pos["current_price"] = 22.5
    signals = check_sell_signals(pos, RiskConfig())
    assert any(s["rule"] == "take_profit" for s in signals)


def test_time_stop():
    pos = _make_position(buy_price=20.0, hold_days=6)
    pos["current_price"] = 20.5
    signals = check_sell_signals(pos, RiskConfig())
    assert any(s["rule"] == "time_stop" for s in signals)


def test_time_stop_not_if_profitable():
    pos = _make_position(buy_price=20.0, hold_days=6)
    pos["current_price"] = 22.5
    signals = check_sell_signals(pos, RiskConfig())
    rules = [s["rule"] for s in signals]
    assert "take_profit" in rules
