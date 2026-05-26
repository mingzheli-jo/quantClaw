from app.main import BUILTIN_STRATEGIES


def test_builtin_strategies_count():
    assert len(BUILTIN_STRATEGIES) == 4


def test_exactly_one_active():
    active = [s for s in BUILTIN_STRATEGIES if s["is_active"]]
    assert len(active) == 1
    assert active[0]["name"] == "稳健短线"


def test_all_have_required_keys():
    required = {"name", "description", "filter_config", "score_config", "signal_config", "risk_config"}
    for s in BUILTIN_STRATEGIES:
        assert required.issubset(s.keys()), f"Missing keys in {s['name']}"


def test_weights_sum_to_one():
    for s in BUILTIN_STRATEGIES:
        sc = s["score_config"]
        total = sc["tech_weight"] + sc["fund_weight"] + sc["momentum_weight"] + sc["sentiment_weight"]
        assert abs(total - 1.0) < 0.01, f"Weights don't sum to 1.0 in {s['name']}: {total}"
