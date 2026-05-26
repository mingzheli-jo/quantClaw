import logging
import httpx

logger = logging.getLogger(__name__)


class FeishuBot:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send_text(self, text: str) -> bool:
        if not self.webhook_url:
            logger.warning("Feishu webhook URL not configured")
            return False
        return self._post({"msg_type": "text", "content": {"text": text}})

    def send_card(self, card: dict) -> bool:
        if not self.webhook_url:
            logger.warning("Feishu webhook URL not configured")
            return False
        return self._post({"msg_type": "interactive", "card": card})

    def _post(self, payload: dict) -> bool:
        try:
            resp = httpx.post(self.webhook_url, json=payload, timeout=10)
            data = resp.json()
            if data.get("code") == 0 or resp.status_code == 200:
                return True
            logger.error(f"Feishu API error: {data}")
            return False
        except Exception as e:
            logger.error(f"Feishu send failed: {e}")
            return False
