import logging
from datetime import date, timedelta

import httpx
from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.signal import Signal
from app.models.stock import StockBasic, StockDaily
from app.models.system import User
from app.services.data.providers.eastmoney import _random_headers
from app.services.data.smart_fetcher import SmartFetcher
from app.services.data.providers.eastmoney import EastmoneyProvider
from app.services.data.providers.baostock_provider import BaostockProvider

logger = logging.getLogger(__name__)

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


@router.get("/quote")
def quote(
    code: str = Query(...),
    user: User = Depends(get_current_user),
):
    market = "1" if code.startswith("6") else "0"
    secid = f"{market}.{code}"
    url = "http://push2.eastmoney.com/api/qt/stock/get"
    params = {
        "secid": secid,
        "fields": "f43,f44,f45,f46,f47,f48,f50,f57,f58,f60,f169,f170,f171",
    }
    try:
        resp = httpx.get(url, params=params, headers=_random_headers(), timeout=5)
        data = resp.json().get("data", {})
        if not data:
            return {"code": code, "price": 0, "change": 0, "change_pct": 0, "volume": 0, "amount": 0, "high": 0, "low": 0, "open": 0, "pre_close": 0}
        divisor = 1000 if data.get("f59", 2) == 3 else 100
        return {
            "code": code,
            "name": data.get("f58", ""),
            "price": (data.get("f43", 0) or 0) / divisor,
            "open": (data.get("f46", 0) or 0) / divisor,
            "high": (data.get("f44", 0) or 0) / divisor,
            "low": (data.get("f45", 0) or 0) / divisor,
            "pre_close": (data.get("f60", 0) or 0) / divisor,
            "change": (data.get("f169", 0) or 0) / divisor,
            "change_pct": (data.get("f170", 0) or 0) / 100,
            "volume": data.get("f47", 0) or 0,
            "amount": (data.get("f48", 0) or 0) / 100,
            "turnover_rate": (data.get("f171", 0) or 0) / 100,
        }
    except Exception as e:
        logger.warning(f"Quote fetch failed for {code}: {e}")
        return {"code": code, "price": 0, "change": 0, "change_pct": 0}


@router.get("/compare")
def compare(
    codes: str = Query(..., description="Comma-separated stock codes, max 4"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    code_list = [c.strip() for c in codes.split(",")][:4]
    results = []
    for code in code_list:
        stock = db.query(StockBasic).filter(StockBasic.code == code).first()
        signal = db.query(Signal).filter(Signal.code == code).order_by(Signal.trade_date.desc()).first()
        klines = (
            db.query(StockDaily)
            .filter(StockDaily.code == code)
            .order_by(StockDaily.trade_date.desc())
            .limit(60)
            .all()
        )
        klines.reverse()
        results.append({
            "code": code,
            "name": stock.name if stock else code,
            "industry": stock.industry if stock else "",
            "score": signal.score if signal else 0,
            "tech_score": signal.tech_score if signal else 0,
            "fund_score": signal.fund_score if signal else 0,
            "momentum_score": signal.momentum_score if signal else 0,
            "sentiment_score": signal.sentiment_score if signal else 0,
            "klines": [
                {"trade_date": str(k.trade_date), "close": k.close, "volume": k.volume, "change_pct": k.change_pct}
                for k in klines
            ],
        })
    return results


def _sync_stock_data(db: Session, code: str, days: int = 90) -> int:
    fetcher = SmartFetcher(primary=EastmoneyProvider(), fallback=BaostockProvider())
    start_date = (date.today() - timedelta(days=days)).strftime("%Y%m%d")
    end_date = date.today().strftime("%Y%m%d")
    df = fetcher.fetch_daily_klines_batch([code], start_date=start_date, end_date=end_date)
    if df.empty:
        return 0
    count = 0
    for _, row in df.iterrows():
        existing = db.query(StockDaily).filter(
            StockDaily.code == row["code"], StockDaily.trade_date == row["trade_date"]
        ).first()
        if not existing:
            db.add(StockDaily(
                code=row["code"], trade_date=row["trade_date"],
                open=row["open"], high=row["high"], low=row["low"], close=row["close"],
                volume=int(row["volume"]), amount=row["amount"],
                change_pct=row.get("change_pct"),
            ))
            count += 1
    if count:
        db.commit()
    logger.info(f"Synced {count} kline rows for {code}")
    return count


@router.post("/{code}/sync")
def sync_stock(
    code: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    count = _sync_stock_data(db, code)
    return {"code": code, "synced": count}


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
    if not items:
        _sync_stock_data(db, code, days=days + 30)
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
