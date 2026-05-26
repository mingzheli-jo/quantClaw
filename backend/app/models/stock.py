from datetime import date, datetime

from sqlalchemy import String, Date, Float, BigInteger, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class StockBasic(Base):
    __tablename__ = "stock_basic"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(20))
    industry: Mapped[str | None] = mapped_column(String(30))
    market: Mapped[str] = mapped_column(String(10))
    list_date: Mapped[date] = mapped_column(Date)
    is_st: Mapped[bool] = mapped_column(default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class StockDaily(Base):
    __tablename__ = "stock_daily"
    __table_args__ = (
        UniqueConstraint("code", "trade_date", name="uq_stock_daily_code_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(10), index=True)
    trade_date: Mapped[date] = mapped_column(Date, index=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[int] = mapped_column(BigInteger)
    amount: Mapped[float] = mapped_column(Float)
    change_pct: Mapped[float | None] = mapped_column(Float)
