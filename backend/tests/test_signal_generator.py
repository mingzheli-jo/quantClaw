import pandas as pd
from app.services.strategy.signal_generator import select_top_n, apply_concentration_control

def test_select_top_n():
    df = pd.DataFrame({"code": ["A", "B", "C", "D"], "score": [90, 85, 70, 50]})
    result = select_top_n(df, min_score=65, top_n=3)
    assert len(result) == 3
    assert result.iloc[0]["code"] == "A"

def test_select_top_n_min_score_filter():
    df = pd.DataFrame({"code": ["A", "B"], "score": [60, 50]})
    result = select_top_n(df, min_score=65, top_n=3)
    assert len(result) == 0

def test_concentration_control():
    df = pd.DataFrame({"code": ["A", "B", "C", "D"], "score": [90, 85, 80, 75], "industry": ["半导体", "半导体", "新能源", "消费"]})
    result = apply_concentration_control(df, held_codes=["E"], top_n=3)
    assert len(result) <= 3
    assert "A" in result["code"].values
    assert "B" not in result["code"].values

def test_concentration_excludes_held():
    df = pd.DataFrame({"code": ["A", "B"], "score": [90, 85], "industry": ["半导体", "新能源"]})
    result = apply_concentration_control(df, held_codes=["A"], top_n=3)
    assert "A" not in result["code"].values
    assert "B" in result["code"].values
