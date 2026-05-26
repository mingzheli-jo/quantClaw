from pydantic import BaseModel


class StrategySettings(BaseModel):
    filter: dict
    score: dict
    position: dict
    risk: dict


class NotifySettings(BaseModel):
    feishu_webhook_url: str


class NotifyTestRequest(BaseModel):
    message: str = "QuantClaw 测试消息 — 飞书推送正常工作!"


class DataSourceSettings(BaseModel):
    source: str
    available: list[str] = []
