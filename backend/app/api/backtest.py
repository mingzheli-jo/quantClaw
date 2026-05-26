import threading
import logging
from datetime import date, timedelta

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.database import SessionLocal
from app.models.stock import StockBasic, StockDaily
from app.models.strategy import StrategyTemplate, BacktestResult
from app.models.system import User
from app.schemas.backtest import BacktestRequest, BacktestOut
from app.services.backtest.engine import BacktestEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


def _run_backtest(backtest_id: int, strategy: dict, start_date: str, end_date: str, initial_capital: float):
    db = SessionLocal()
    try:
        bt = db.query(BacktestResult).filter(BacktestResult.id == backtest_id).first()
        if not bt:
            return

        start_d = date.fromisoformat(start_date)
        end_d = date.fromisoformat(end_date)

        stocks = db.query(StockBasic).all()
        stocks_df = pd.DataFrame([
            {"code": s.code, "name": s.name, "market": s.market, "is_st": s.is_st,
             "list_date": s.list_date or date(2020, 1, 1), "industry": s.industry or ""}
            for s in stocks
        ])

        if stocks_df.empty:
            bt.status = "failed"
            bt.error_message = "No stock data in database. Run seed_data first."
            db.commit()
            return

        klines = db.query(StockDaily).filter(
            StockDaily.trade_date >= start_d - timedelta(days=60),
            StockDaily.trade_date <= end_d,
        ).all()

        if not klines:
            bt.status = "failed"
            bt.error_message = "No K-line data available for the selected date range."
            db.commit()
            return

        kline_df = pd.DataFrame([
            {"code": k.code, "trade_date": k.trade_date, "open": k.open, "high": k.high,
             "low": k.low, "close": k.close, "volume": k.volume, "amount": k.amount,
             "change_pct": k.change_pct or 0}
            for k in klines
        ])

        engine = BacktestEngine(
            stocks_df=stocks_df, kline_df=kline_df,
            strategy_config=strategy,
            start_date=start_d, end_date=end_d,
            initial_capital=initial_capital,
        )
        result = engine.run()

        bt.status = "completed"
        bt.summary = result["summary"]
        bt.daily_values = result["daily_values"]
        bt.trades = result["trades"]
        db.commit()

    except Exception as e:
        logger.error(f"Backtest {backtest_id} failed: {e}")
        try:
            bt = db.query(BacktestResult).filter(BacktestResult.id == backtest_id).first()
            if bt:
                bt.status = "failed"
                bt.error_message = str(e)
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


@router.post("/run", response_model=BacktestOut, status_code=201)
def run_backtest(body: BacktestRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    strategy = db.query(StrategyTemplate).filter(StrategyTemplate.id == body.strategy_id).first()
    if not strategy:
        raise HTTPException(404, "Strategy not found")

    bt = BacktestResult(
        strategy_id=strategy.id,
        strategy_name=strategy.name,
        start_date=body.start_date,
        end_date=body.end_date,
        initial_capital=body.initial_capital,
        status="running",
    )
    db.add(bt)
    db.commit()
    db.refresh(bt)

    strategy_config = {
        "filter_config": strategy.filter_config,
        "score_config": strategy.score_config,
        "signal_config": strategy.signal_config,
        "risk_config": strategy.risk_config,
    }

    thread = threading.Thread(
        target=_run_backtest,
        args=(bt.id, strategy_config, body.start_date, body.end_date, body.initial_capital),
        daemon=True,
    )
    thread.start()

    return bt


@router.get("/list", response_model=list[BacktestOut])
def list_backtests(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(BacktestResult).order_by(BacktestResult.id.desc()).limit(20).all()


@router.get("/{backtest_id}", response_model=BacktestOut)
def get_backtest(backtest_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    bt = db.query(BacktestResult).filter(BacktestResult.id == backtest_id).first()
    if not bt:
        raise HTTPException(404, "Backtest not found")
    return bt


@router.delete("/{backtest_id}")
def delete_backtest(backtest_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    bt = db.query(BacktestResult).filter(BacktestResult.id == backtest_id).first()
    if not bt:
        raise HTTPException(404, "Backtest not found")
    db.delete(bt)
    db.commit()
    return {"ok": True}
