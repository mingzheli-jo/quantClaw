import logging
import time

import httpx

logger = logging.getLogger(__name__)

_PROVIDER_CONFIG = {
    "deepseek": {
        "url": "https://api.deepseek.com/chat/completions",
        "model": "deepseek-chat",
    },
    "qwen": {
        "url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "model": "qwen-plus",
    },
}

_MAX_RETRIES = 2
_RETRY_DELAY = 3
_TIMEOUT = 30


class LLMClient:
    def __init__(self, api_key: str, provider: str = "deepseek"):
        self._api_key = api_key
        self._provider = provider
        cfg = _PROVIDER_CONFIG.get(provider, _PROVIDER_CONFIG["deepseek"])
        self._url = cfg["url"]
        self._model = cfg["model"]

    def chat(self, messages: list[dict], temperature: float = 0.3) -> str:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 1024,
        }
        for attempt in range(_MAX_RETRIES + 1):
            try:
                resp = httpx.post(self._url, json=payload, headers=headers, timeout=_TIMEOUT)
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            except Exception as e:
                logger.warning(f"LLM call attempt {attempt + 1} failed: {e}")
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_DELAY)
        logger.error("LLM call failed after all retries")
        return ""
