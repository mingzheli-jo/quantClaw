from datetime import date
from pydantic import BaseModel


class SignalItem(BaseModel):
    id: int
    code: str
    stock_name: str
    trade_date: date
    direction: str
    score: int
    reason: str
    close_price: float
    suggested_buy_low: float | None
    suggested_buy_high: float | None
    stop_loss_price: float | None
    target_price: float | None

    class Config:
        from_attributes = True
