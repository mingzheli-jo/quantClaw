from app.services.strategy.scoring import compute_total_score


def test_default_weights_backward_compatible():
    scores = {"tech": 30, "fund": 20, "momentum": 15, "sentiment": 8}
    result = compute_total_score(scores)
    assert result == 73


def test_weighted_scoring():
    scores = {"tech": 40, "fund": 0, "momentum": 0, "sentiment": 0}
    weights = {"tech_weight": 1.0, "fund_weight": 0.0, "momentum_weight": 0.0, "sentiment_weight": 0.0}
    result = compute_total_score(scores, weights)
    assert result == 100


def test_balanced_weights():
    scores = {"tech": 20, "fund": 15, "momentum": 10, "sentiment": 5}
    weights = {"tech_weight": 0.25, "fund_weight": 0.25, "momentum_weight": 0.25, "sentiment_weight": 0.25}
    result = compute_total_score(scores, weights)
    assert result == 50
