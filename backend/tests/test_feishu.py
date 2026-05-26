from unittest.mock import patch, MagicMock
from app.services.notify.feishu import FeishuBot


@patch("app.services.notify.feishu.httpx")
def test_send_text(mock_httpx):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"code": 0}
    mock_httpx.post.return_value = mock_response
    bot = FeishuBot("https://fake-webhook-url")
    result = bot.send_text("hello")
    assert result is True
    mock_httpx.post.assert_called_once()


@patch("app.services.notify.feishu.httpx")
def test_send_card(mock_httpx):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"code": 0}
    mock_httpx.post.return_value = mock_response
    bot = FeishuBot("https://fake-webhook-url")
    card = {
        "header": {"title": {"tag": "plain_text", "content": "Test"}},
        "elements": [{"tag": "div", "text": {"tag": "plain_text", "content": "body"}}],
    }
    result = bot.send_card(card)
    assert result is True


def test_send_text_no_url():
    bot = FeishuBot("")
    result = bot.send_text("hello")
    assert result is False
