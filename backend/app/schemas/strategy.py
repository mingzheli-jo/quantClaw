from pydantic import BaseModel
from datetime import datetime


class FilterConfig(BaseModel):
    min_amount_20d: int = 50_000_000
    max_price: float = 50
    min_list_days: int = 60
    exclude_bj: bool = True


class ScoreConfig(BaseModel):
    tech_weight: float = 0.4
    fund_weight: float = 0.3
    momentum_weight: float = 0.2
    sentiment_weight: float = 0.1
    ma_periods: list[int] = [5, 10, 20]
    macd_enabled: bool = True
    kdj_enabled: bool = True
    bollinger_enabled: bool = True
    volume_ratio_threshold: float = 1.5


class SignalConfig(BaseModel):
    min_score: int = 65
    top_n: int = 3
    concentration_control: bool = True


class RiskConfig(BaseModel):
    stop_loss_pct: float = -0.05
    take_profit_pct: float = 0.12
    trailing_trigger: float = 0.07
    trailing_drawdown: float = 0.03
    max_hold_days: int = 5


class StrategyCreate(BaseModel):
    name: str
    description: str = ""
    filter_config: FilterConfig = FilterConfig()
    score_config: ScoreConfig = ScoreConfig()
    signal_config: SignalConfig = SignalConfig()
    risk_config: RiskConfig = RiskConfig()


class StrategyUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    filter_config: FilterConfig | None = None
    score_config: ScoreConfig | None = None
    signal_config: SignalConfig | None = None
    risk_config: RiskConfig | None = None


class StrategyOut(BaseModel):
    id: int
    name: str
    description: str
    filter_config: dict
    score_config: dict
    signal_config: dict
    risk_config: dict
    is_active: bool
    is_builtin: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True
