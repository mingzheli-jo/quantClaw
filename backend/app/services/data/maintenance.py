import logging
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models.stock import StockDaily, StockBasic
from app.models.market import NorthFlow, SectorDaily, FundFlow, MarketSentiment

logger = logging.getLogger(__name__)


def update_stock_basic(db: Session):
    from app.services.data.fetcher import fetch_stock_basic_list

    df = fetch_stock_basic_list()
    if df.empty:
        return
    for _, row in df.iterrows():
        existing = db.query(StockBasic).filter(StockBasic.code == row["code"]).first()
        if existing:
            existing.name = row["name"]
            existing.is_st = row["is_st"]
            existing.market = row["market"]
            if row.get("industry"):
                existing.industry = row["industry"]
        else:
            db.add(StockBasic(
                code=row["code"], name=row["name"], market=row["market"],
                is_st=row["is_st"], list_date=row.get("list_date") or date.today(),
                industry=row.get("industry"),
            ))
    db.commit()


def purge_old_data(db: Session, keep_days: int = 365):
    cutoff = date.today() - timedelta(days=keep_days)
    tables_and_date_cols = [
        (StockDaily, StockDaily.trade_date),
        (NorthFlow, NorthFlow.trade_date),
        (SectorDaily, SectorDaily.trade_date),
        (FundFlow, FundFlow.trade_date),
        (MarketSentiment, MarketSentiment.trade_date),
    ]
    for model, col in tables_and_date_cols:
        deleted = db.query(model).filter(col < cutoff).delete(synchronize_session=False)
        if deleted:
            logger.info(f"Purged {deleted} rows from {model.__tablename__} older than {cutoff}")
    db.commit()
