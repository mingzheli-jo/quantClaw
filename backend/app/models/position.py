from datetime import date, datetime

from sqlalchemy import String, Date, Float, Integer, Text, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Position(Base):
    __tablename__ = "position"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(10), index=True)
    stock_name: Mapped[str] = mapped_column(String(20))
    buy_date: Mapped[date] = mapped_column(Date)
    buy_price: Mapped[float] = mapped_column(Float)
    shares: Mapped[int] = mapped_column(Integer)
    cost_amount: Mapped[float] = mapped_column(Float)
    stop_loss_price: Mapped[float] = mapped_column(Float)
    take_profit_price: Mapped[float] = mapped_column(Float)
    highest_price: Mapped[float] = mapped_column(Float)
    current_price: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(10), default="open")
    close_date: Mapped[date | None] = mapped_column(Date)
    close_price: Mapped[float | None] = mapped_column(Float)
    close_reason: Mapped[str | None] = mapped_column(String(30))
    pnl: Mapped[float | None] = mapped_column(Float)
    pnl_pct: Mapped[float | None] = mapped_column(Float)
    executed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class TradeLog(Base):
    __tablename__ = "trade_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(10), index=True)
    stock_name: Mapped[str] = mapped_column(String(20))
    trade_date: Mapped[date] = mapped_column(Date, index=True)
    action: Mapped[str] = mapped_column(String(4))
    price: Mapped[float] = mapped_column(Float)
    shares: Mapped[int] = mapped_column(Integer)
    amount: Mapped[float] = mapped_column(Float)
    fee: Mapped[float] = mapped_column(Float, default=0.0)
    reason: Mapped[str] = mapped_column(Text)
    position_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
