from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.signal import Signal
from app.models.stock import StockBasic, StockDaily
from app.models.system import User

router = APIRouter(prefix="/api/stock", tags=["stock"])


@router.get("/search")
def search(
    q: str = Query(..., min_length=1, max_length=20),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    pattern = f"%{q}%"
    results = (
        db.query(StockBasic)
        .filter(or_(StockBasic.code.like(pattern), StockBasic.name.like(pattern)))
        .limit(20)
        .all()
    )
    return [
        {
            "code": s.code,
            "name": s.name,
            "market": s.market,
            "industry": s.industry or "",
        }
        for s in results
    ]


@router.get("/{code}/kline")
def kline(
    code: str,
    days: int = Query(60, ge=1, le=250),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    cutoff = date.today() - timedelta(days=int(days * 1.5))
    items = (
        db.query(StockDaily)
        .filter(StockDaily.code == code, StockDaily.trade_date >= cutoff)
        .order_by(StockDaily.trade_date)
        .all()
    )
    return [
        {
            "trade_date": str(k.trade_date),
            "open": k.open,
            "high": k.high,
            "low": k.low,
            "close": k.close,
            "volume": k.volume,
        }
        for k in items
    ]


@router.get("/{code}/signals")
def signals(
    code: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = (
        db.query(Signal)
        .filter(Signal.code == code)
        .order_by(Signal.trade_date.desc())
        .limit(30)
        .all()
    )
    return [
        {
            "trade_date": str(s.trade_date),
            "direction": s.direction,
            "score": s.score,
            "reason": s.reason,
        }
        for s in items
    ]


@router.get("/{code}/score")
def score(
    code: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    s = db.query(Signal).filter(Signal.code == code).order_by(Signal.trade_date.desc()).first()
    if not s:
        return {"code": code, "score": 0, "detail": "无评分数据"}
    return {
        "code": s.code,
        "stock_name": s.stock_name,
        "score": s.score,
        "tech_score": s.tech_score,
        "fund_score": s.fund_score,
        "momentum_score": s.momentum_score,
        "sentiment_score": s.sentiment_score,
        "reason": s.reason,
    }
