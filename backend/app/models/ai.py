from datetime import date, datetime

from sqlalchemy import String, Date, Text, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AIAnalysis(Base):
    __tablename__ = "ai_analysis"
    __table_args__ = (UniqueConstraint("code", "trade_date", name="uq_ai_analysis_code_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(10), index=True)
    trade_date: Mapped[date] = mapped_column(Date, index=True)
    summary: Mapped[str | None] = mapped_column(Text)
    risk: Mapped[str | None] = mapped_column(Text)
    suggestion: Mapped[str | None] = mapped_column(Text)
    market_comment: Mapped[str | None] = mapped_column(Text)
    llm_provider: Mapped[str] = mapped_column(String(20), default="deepseek")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
