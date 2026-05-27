"""
QuantClaw Data Seeder
Pulls real A-share market data via configured provider (EastMoney/BaoStock) and populates the database.
Run: cd backend && python -m scripts.seed_data
"""
import sys
import os
import time
import logging
from datetime import date, timedelta

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DATABASE_URL", "postgresql://cptop:cptop@localhost:5432/quantclaw")
os.environ.setdefault("SECRET_KEY", "dev-secret")
os.environ.setdefault("ADMIN_PASSWORD", "admin123")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

from app.database import Base, engine, SessionLocal
from app.models import *
from app.services.data.providers.base import DataSourceManager
from app.services.data.providers.eastmoney import EastmoneyProvider
from app.services.data.providers.baostock_provider import BaostockProvider

DataSourceManager.register("eastmoney", EastmoneyProvider())
DataSourceManager.register("baostock", BaostockProvider())

SEED_SOURCE = os.environ.get("SEED_SOURCE", "baostock")
DataSourceManager.set_source(SEED_SOURCE)
logger.info(f"Data source forced to: {SEED_SOURCE}")

from app.services.data.fetcher import (
    fetch_stock_basic_list,
    fetch_daily_klines_batch,
    fetch_north_flow,
    fetch_sector_daily,
    fetch_market_sentiment,
)
from app.services.data.indicators import calc_volume_ratio
from app.services.strategy.filters import hard_filter
from app.services.strategy.scoring import score_technical, score_fund, score_momentum, score_sentiment
from app.services.strategy.signal_generator import select_top_n, apply_concentration_control, build_signal_reason
from app.utils.security import hash_password
import pandas as pd


def seed():
    logger.info("=== QuantClaw Data Seeder ===")

    # 1. Create tables
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # Seed admin user
        if not db.query(User).filter(User.username == "admin").first():
            db.add(User(username="admin", hashed_password=hash_password("admin123")))
            db.commit()
            logger.info("Admin user created")

        # 2. Fetch stock basic list
        logger.info("Fetching stock basic list from AKShare...")
        stock_df = fetch_stock_basic_list()
        if stock_df.empty:
            logger.error("Failed to fetch stock list!")
            return
        logger.info(f"Got {len(stock_df)} stocks")

        # Insert stock_basic records
        count = 0
        for _, row in stock_df.iterrows():
            existing = db.query(StockBasic).filter(StockBasic.code == row["code"]).first()
            if not existing:
                db.add(StockBasic(
                    code=row["code"],
                    name=row["name"],
                    market=row["market"],
                    is_st=bool(row["is_st"]),
                    list_date=row.get("list_date") or date(2020, 1, 1),
                    industry=row.get("industry"),
                ))
                count += 1
        db.commit()
        logger.info(f"Inserted {count} new stock_basic records")

        # 3. Fetch K-line data for a subset (top 200 by market cap / popular stocks)
        # Use all SH/SZ main board stocks that are not ST, pick first 200
        popular = stock_df[
            (~stock_df["is_st"]) &
            (stock_df["market"].isin(["sh", "sz"]))
        ].head(200)
        codes = popular["code"].tolist()
        logger.info(f"Fetching K-line data for {len(codes)} stocks (past 60 days)...")

        start_date = (date.today() - timedelta(days=90)).strftime("%Y%m%d")
        end_date = date.today().strftime("%Y%m%d")

        kline_df = fetch_daily_klines_batch(codes, start_date=start_date, end_date=end_date)
        if not kline_df.empty:
            kline_count = 0
            for _, row in kline_df.iterrows():
                existing = db.query(StockDaily).filter(
                    StockDaily.code == row["code"],
                    StockDaily.trade_date == row["trade_date"]
                ).first()
                if not existing:
                    db.add(StockDaily(
                        code=row["code"],
                        trade_date=row["trade_date"],
                        open=row["open"],
                        high=row["high"],
                        low=row["low"],
                        close=row["close"],
                        volume=int(row["volume"]),
                        amount=row["amount"],
                        change_pct=row.get("change_pct"),
                    ))
                    kline_count += 1
                    if kline_count % 1000 == 0:
                        db.commit()
                        logger.info(f"  ...inserted {kline_count} K-line rows")
            db.commit()
            logger.info(f"Inserted {kline_count} total K-line rows")
        else:
            logger.warning("No K-line data fetched")

        # 4. Fetch north flow
        logger.info("Fetching north flow data...")
        north_df = fetch_north_flow(days=30)
        if not north_df.empty:
            north_count = 0
            for _, row in north_df.iterrows():
                existing = db.query(NorthFlow).filter(NorthFlow.trade_date == row["trade_date"]).first()
                if not existing:
                    db.add(NorthFlow(
                        trade_date=row["trade_date"],
                        buy_amount=row["buy_amount"],
                        sell_amount=row["sell_amount"],
                        net_amount=row["net_amount"],
                    ))
                    north_count += 1
            db.commit()
            logger.info(f"Inserted {north_count} north flow records")

        # 5. Fetch sector daily
        logger.info("Fetching sector data...")
        sector_df = fetch_sector_daily()
        if not sector_df.empty:
            sector_count = 0
            for _, row in sector_df.iterrows():
                existing = db.query(SectorDaily).filter(
                    SectorDaily.sector == row["sector"],
                    SectorDaily.trade_date == row["trade_date"]
                ).first()
                if not existing:
                    db.add(SectorDaily(
                        sector=row["sector"],
                        trade_date=row["trade_date"],
                        change_pct=float(row.get("change_pct", 0)),
                        volume=int(row.get("volume", 0)),
                        net_fund_flow=float(row.get("net_fund_flow", 0)),
                    ))
                    sector_count += 1
            db.commit()
            logger.info(f"Inserted {sector_count} sector records")

        # 6. Fetch market sentiment
        logger.info("Fetching market sentiment...")
        sentiment = fetch_market_sentiment()
        if sentiment:
            existing = db.query(MarketSentiment).filter(
                MarketSentiment.trade_date == sentiment["trade_date"]
            ).first()
            if not existing:
                db.add(MarketSentiment(**sentiment))
                db.commit()
                logger.info("Inserted market sentiment")

        # 7. Run scoring pipeline
        logger.info("Running scoring pipeline...")
        today = date.today()

        basics = db.query(StockBasic).filter(StockBasic.code.in_(codes)).all()
        stocks = []
        for b in basics:
            last_20 = db.query(StockDaily).filter(
                StockDaily.code == b.code
            ).order_by(StockDaily.trade_date.desc()).limit(20).all()
            if len(last_20) < 5:
                continue
            latest = last_20[0]
            avg_amount = sum(d.amount for d in last_20) / len(last_20)
            pct_5d = 0
            if len(last_20) >= 5:
                pct_5d = (latest.close - last_20[4].close) / last_20[4].close * 100
            stocks.append({
                "code": b.code, "name": b.name, "close": latest.close,
                "avg_amount_20d": avg_amount, "list_date": b.list_date or date(2020, 1, 1),
                "market": b.market, "is_st": b.is_st,
                "is_suspended": False,
                "is_limit_up": (latest.change_pct or 0) >= 9.9,
                "is_limit_down": (latest.change_pct or 0) <= -9.9,
                "industry": b.industry or "未知", "pct_5d": pct_5d,
            })

        if stocks:
            universe_df = pd.DataFrame(stocks)
            config = {"min_amount_20d": 50_000_000, "max_price": 50, "min_list_days": 60}
            filtered = hard_filter(universe_df, config)
            logger.info(f"After hard filter: {len(filtered)} stocks from {len(universe_df)}")

            scored_rows = []
            for idx, (_, row) in enumerate(filtered.iterrows()):
                klines = db.query(StockDaily).filter(
                    StockDaily.code == row["code"]
                ).order_by(StockDaily.trade_date).all()
                kline_df_local = pd.DataFrame([
                    {"open": k.open, "high": k.high, "low": k.low, "close": k.close, "volume": k.volume}
                    for k in klines
                ])
                if len(kline_df_local) < 20:
                    continue

                tech_score, tech_details = score_technical(kline_df_local)
                vol_ratio = calc_volume_ratio(kline_df_local["volume"], 20)
                fund_data = {"north_net_3d": 0, "main_net": 0, "super_large_pct": 0, "volume_ratio": vol_ratio}
                fund_score, fund_details = score_fund(fund_data)

                sector_row_db = db.query(SectorDaily).filter(
                    SectorDaily.sector == row["industry"],
                    SectorDaily.trade_date == today
                ).first()
                sector_rank_pct = 50
                momentum_data = {
                    "pct_5d": row["pct_5d"],
                    "relative_strength": row["pct_5d"],
                    "is_20d_high": row["close"] >= kline_df_local["close"].tail(20).max()
                }
                momentum_score, momentum_details = score_momentum(momentum_data)

                sentiment_row_db = db.query(MarketSentiment).filter(
                    MarketSentiment.trade_date == today
                ).first()
                sentiment_data = {
                    "sector_rank_pct": sector_rank_pct,
                    "limit_up": sentiment_row_db.limit_up if sentiment_row_db else 30,
                    "limit_down": sentiment_row_db.limit_down if sentiment_row_db else 10,
                    "sector_net_flow": sector_row_db.net_fund_flow if sector_row_db else 0,
                }
                sentiment_score, sentiment_details = score_sentiment(sentiment_data)

                total = tech_score + fund_score + momentum_score + sentiment_score
                all_details = {"tech": tech_details, "fund": fund_details, "momentum": momentum_details, "sentiment": sentiment_details}
                reason = build_signal_reason(all_details)

                scored_rows.append({
                    "code": row["code"], "stock_name": row["name"], "close": row["close"],
                    "industry": row["industry"], "score": total,
                    "tech_score": tech_score, "fund_score": fund_score,
                    "momentum_score": momentum_score, "sentiment_score": sentiment_score,
                    "reason": reason,
                })

                if (idx + 1) % 20 == 0:
                    logger.info(f"  ...scored {idx + 1} stocks")

            logger.info(f"Scored {len(scored_rows)} stocks total")

            # Save ALL scored stocks as signals (not just top 3) so the ranking page has data
            for sig in scored_rows:
                db.add(Signal(
                    code=sig["code"], stock_name=sig["stock_name"], trade_date=today,
                    direction="buy", score=sig["score"],
                    tech_score=sig["tech_score"], fund_score=sig["fund_score"],
                    momentum_score=sig["momentum_score"], sentiment_score=sig["sentiment_score"],
                    reason=sig["reason"], close_price=sig["close"],
                    suggested_buy_low=round(sig["close"] * 0.99, 2),
                    suggested_buy_high=round(sig["close"] * 1.01, 2),
                    stop_loss_price=round(sig["close"] * 0.95, 2),
                    target_price=round(sig["close"] * 1.12, 2),
                ))
            db.commit()
            logger.info(f"Saved {len(scored_rows)} signals to database")

            # Print top 10
            scored_df = pd.DataFrame(scored_rows).sort_values("score", ascending=False)
            logger.info("\n=== TOP 10 Signals ===")
            for i, (_, row) in enumerate(scored_df.head(10).iterrows()):
                logger.info(f"  {i+1}. {row['stock_name']} ({row['code']}) Score: {row['score']} | {row['reason']}")

        logger.info("\n=== Data seeding complete! ===")
        total_stocks = db.query(StockBasic).count()
        total_klines = db.query(StockDaily).count()
        total_signals = db.query(Signal).count()
        total_sectors = db.query(SectorDaily).count()
        total_north = db.query(NorthFlow).count()
        logger.info(f"  Stocks: {total_stocks}")
        logger.info(f"  K-lines: {total_klines}")
        logger.info(f"  Signals: {total_signals}")
        logger.info(f"  Sectors: {total_sectors}")
        logger.info(f"  North flow: {total_north}")

    finally:
        db.close()


if __name__ == "__main__":
    seed()
