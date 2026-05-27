from unittest.mock import patch, MagicMock
from app.services.ai.llm_client import LLMClient


def test_chat_returns_string():
    client = LLMClient(api_key="test-key", provider="deepseek")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "test response"}}]
    }
    with patch("httpx.post", return_value=mock_resp):
        result = client.chat([{"role": "user", "content": "hello"}])
    assert result == "test response"


def test_chat_retries_on_failure():
    client = LLMClient(api_key="test-key", provider="deepseek")
    mock_ok = MagicMock()
    mock_ok.status_code = 200
    mock_ok.json.return_value = {
        "choices": [{"message": {"content": "ok"}}]
    }
    with patch("httpx.post", side_effect=[Exception("timeout"), mock_ok]):
        result = client.chat([{"role": "user", "content": "hello"}])
    assert result == "ok"


def test_chat_returns_empty_after_all_retries():
    client = LLMClient(api_key="test-key", provider="deepseek")
    with patch("httpx.post", side_effect=Exception("timeout")):
        result = client.chat([{"role": "user", "content": "hello"}])
    assert result == ""
