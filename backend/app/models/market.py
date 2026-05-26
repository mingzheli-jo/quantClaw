from datetime import date

from sqlalchemy import String, Date, Float, BigInteger, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class NorthFlow(Base):
    __tablename__ = "north_flow"

    id: Mapped[int] = mapped_column(primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, unique=True, index=True)
    buy_amount: Mapped[float] = mapped_column(Float)
    sell_amount: Mapped[float] = mapped_column(Float)
    net_amount: Mapped[float] = mapped_column(Float)


class SectorDaily(Base):
    __tablename__ = "sector_daily"
    __table_args__ = (
        UniqueConstraint("sector", "trade_date", name="uq_sector_daily"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sector: Mapped[str] = mapped_column(String(30), index=True)
    trade_date: Mapped[date] = mapped_column(Date, index=True)
    change_pct: Mapped[float] = mapped_column(Float)
    volume: Mapped[int] = mapped_column(BigInteger, default=0)
    net_fund_flow: Mapped[float] = mapped_column(Float, default=0.0)


class FundFlow(Base):
    __tablename__ = "fund_flow"
    __table_args__ = (
        UniqueConstraint("code", "trade_date", name="uq_fund_flow"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(10), index=True)
    trade_date: Mapped[date] = mapped_column(Date, index=True)
    main_net: Mapped[float] = mapped_column(Float, default=0.0)
    super_large_net: Mapped[float] = mapped_column(Float, default=0.0)
    large_net: Mapped[float] = mapped_column(Float, default=0.0)
    medium_net: Mapped[float] = mapped_column(Float, default=0.0)
    small_net: Mapped[float] = mapped_column(Float, default=0.0)


class MarketSentiment(Base):
    __tablename__ = "market_sentiment"

    id: Mapped[int] = mapped_column(primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, unique=True, index=True)
    up_count: Mapped[int] = mapped_column(Integer)
    down_count: Mapped[int] = mapped_column(Integer)
    flat_count: Mapped[int] = mapped_column(Integer, default=0)
    limit_up: Mapped[int] = mapped_column(Integer)
    limit_down: Mapped[int] = mapped_column(Integer)
    sh_index_pct: Mapped[float] = mapped_column(Float, default=0.0)
    sz_index_pct: Mapped[float] = mapped_column(Float, default=0.0)
    cyb_index_pct: Mapped[float] = mapped_column(Float, default=0.0)
