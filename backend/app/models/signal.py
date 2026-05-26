from datetime import date, datetime

from sqlalchemy import String, Date, Float, Integer, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Signal(Base):
    __tablename__ = "signal"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(10), index=True)
    stock_name: Mapped[str] = mapped_column(String(20))
    trade_date: Mapped[date] = mapped_column(Date, index=True)
    direction: Mapped[str] = mapped_column(String(4))
    score: Mapped[int] = mapped_column(Integer)
    tech_score: Mapped[int] = mapped_column(Integer, default=0)
    fund_score: Mapped[int] = mapped_column(Integer, default=0)
    momentum_score: Mapped[int] = mapped_column(Integer, default=0)
    sentiment_score: Mapped[int] = mapped_column(Integer, default=0)
    reason: Mapped[str] = mapped_column(Text)
    close_price: Mapped[float] = mapped_column(Float)
    suggested_buy_low: Mapped[float | None] = mapped_column(Float)
    suggested_buy_high: Mapped[float | None] = mapped_column(Float)
    stop_loss_price: Mapped[float | None] = mapped_column(Float)
    target_price: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
