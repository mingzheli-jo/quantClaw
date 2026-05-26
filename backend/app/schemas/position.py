from datetime import date

from pydantic import BaseModel


class PositionCreate(BaseModel):
    code: str
    stock_name: str
    buy_price: float
    shares: int
    buy_date: date | None = None


class PositionClose(BaseModel):
    close_price: float
    close_reason: str = "manual"
    close_date: date | None = None


class PositionItem(BaseModel):
    id: int
    code: str
    stock_name: str
    buy_date: date
    buy_price: float
    shares: int
    cost_amount: float
    current_price: float | None
    highest_price: float
    pnl_pct: float | None
    status: str
    hold_days: int
    stop_loss_price: float
    take_profit_price: float
    executed: bool

    class Config:
        from_attributes = True


class TradeItem(BaseModel):
    id: int
    code: str
    stock_name: str
    trade_date: date
    action: str
    price: float
    shares: int
    amount: float
    fee: float
    reason: str

    class Config:
        from_attributes = True


class PositionStats(BaseModel):
    total_trades: int
    win_count: int
    loss_count: int
    win_rate: float
    total_pnl: float
    avg_pnl_pct: float
    avg_hold_days: float
