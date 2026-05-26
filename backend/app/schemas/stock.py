from datetime import date
from pydantic import BaseModel


class KLineItem(BaseModel):
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    volume: int
    amount: float


class StockScore(BaseModel):
    code: str
    stock_name: str
    total_score: int
    tech_score: int
    fund_score: int
    momentum_score: int
    sentiment_score: int
    reason: str
    close_price: float
    industry: str | None = None
