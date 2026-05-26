from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, JSON, Text, func
from app.database import Base


class StrategyTemplate(Base):
    __tablename__ = "strategy_template"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, default="")
    filter_config = Column(JSON, nullable=False)
    score_config = Column(JSON, nullable=False)
    signal_config = Column(JSON, nullable=False)
    risk_config = Column(JSON, nullable=False)
    is_active = Column(Boolean, default=False)
    is_builtin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class BacktestResult(Base):
    __tablename__ = "backtest_result"

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_id = Column(Integer, nullable=False)
    strategy_name = Column(String(100), nullable=False)
    start_date = Column(String(10), nullable=False)
    end_date = Column(String(10), nullable=False)
    initial_capital = Column(Float, nullable=False, default=50000)
    status = Column(String(20), nullable=False, default="running")
    error_message = Column(Text, nullable=True)
    summary = Column(JSON, nullable=True)
    daily_values = Column(JSON, nullable=True)
    trades = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=func.now())
