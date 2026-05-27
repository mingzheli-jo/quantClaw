import json
from unittest.mock import patch, MagicMock

from app.services.ai.analyzer import build_stock_context, analyze_stock


def test_build_stock_context():
    db = MagicMock()
    signal = MagicMock()
    signal.code = "000001"
    signal.stock_name = "平安银行"
    signal.score = 72
    signal.tech_score = 28
    signal.fund_score = 22
    signal.momentum_score = 14
    signal.sentiment_score = 8
    signal.reason = "MA5上穿MA20"
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = signal
    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
    db.query.return_value.filter.return_value.first.return_value = None

    ctx = build_stock_context(db, "000001")
    assert ctx["code"] == "000001"
    assert ctx["scores"]["total"] == 72
    assert ctx["reason"] == "MA5上穿MA20"


def test_analyze_stock_parses_json():
    db = MagicMock()
    mock_ctx = {"code": "000001", "name": "Test", "scores": {}, "reason": ""}
    llm_response = json.dumps({
        "summary": "test summary",
        "risk": "test risk",
        "suggestion": "test suggestion",
        "market_comment": "test comment",
    })
    with patch("app.services.ai.analyzer.build_stock_context", return_value=mock_ctx):
        with patch("app.services.ai.analyzer._get_llm_client") as mock_llm:
            mock_llm.return_value.chat.return_value = llm_response
            result = analyze_stock(db, "000001")
    assert result["summary"] == "test summary"
    assert result["risk"] == "test risk"


def test_analyze_stock_handles_malformed_response():
    db = MagicMock()
    mock_ctx = {"code": "000001", "name": "Test", "scores": {}, "reason": ""}
    with patch("app.services.ai.analyzer.build_stock_context", return_value=mock_ctx):
        with patch("app.services.ai.analyzer._get_llm_client") as mock_llm:
            mock_llm.return_value.chat.return_value = "not json, just plain text analysis"
            result = analyze_stock(db, "000001")
    assert result["summary"] == "not json, just plain text analysis"
    assert result["risk"] == ""
