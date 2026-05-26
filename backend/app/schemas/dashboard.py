from pydantic import BaseModel


class DashboardOverview(BaseModel):
    temperature: int
    sh_index_pct: float
    sz_index_pct: float
    cyb_index_pct: float
    limit_up: int
    limit_down: int
    north_net: float
    active_positions: int
    total_pnl: float
    signal_accuracy_7d: float


class SentimentData(BaseModel):
    up_count: int
    down_count: int
    limit_up: int
    limit_down: int
    temperature: int
