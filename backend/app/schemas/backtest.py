from pydantic import BaseModel
from datetime import datetime


class BacktestRequest(BaseModel):
    strategy_id: int
    start_date: str
    end_date: str
    initial_capital: float = 50000


class BacktestOut(BaseModel):
    id: int
    strategy_id: int
    strategy_name: str
    start_date: str
    end_date: str
    initial_capital: float
    status: str
    error_message: str | None = None
    summary: dict | None = None
    daily_values: list | None = None
    trades: list | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True
