from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.signal import Signal
from app.models.stock import StockBasic, StockDaily
from app.models.system import User
from app.models.watchlist import Watchlist

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


class WatchlistAdd(BaseModel):
    code: str
    note: str | None = None


@router.get("")
def list_watchlist(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = db.query(Watchlist).filter(Watchlist.user_id == user.id).order_by(Watchlist.added_at.desc()).all()
    result = []
    for item in items:
        stock = db.query(StockBasic).filter(StockBasic.code == item.code).first()
        latest = db.query(StockDaily).filter(StockDaily.code == item.code).order_by(StockDaily.trade_date.desc()).first()
        signal = db.query(Signal).filter(Signal.code == item.code).order_by(Signal.trade_date.desc()).first()
        result.append({
            "code": item.code,
            "name": stock.name if stock else item.code,
            "industry": stock.industry if stock else "",
            "close": latest.close if latest else 0,
            "change_pct": latest.change_pct if latest else 0,
            "score": signal.score if signal else 0,
            "note": item.note,
            "added_at": str(item.added_at),
        })
    return result


@router.post("")
def add_to_watchlist(
    body: WatchlistAdd,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    existing = db.query(Watchlist).filter(
        Watchlist.user_id == user.id, Watchlist.code == body.code
    ).first()
    if existing:
        return {"code": existing.code, "note": existing.note, "added_at": str(existing.added_at)}
    item = Watchlist(user_id=user.id, code=body.code, note=body.note)
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"code": item.code, "note": item.note, "added_at": str(item.added_at)}


@router.delete("/{code}")
def remove_from_watchlist(
    code: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = db.query(Watchlist).filter(
        Watchlist.user_id == user.id, Watchlist.code == code
    ).first()
    if item:
        db.delete(item)
        db.commit()
    return {"ok": True}


@router.get("/signals")
def watchlist_signals(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    codes = [w.code for w in db.query(Watchlist).filter(Watchlist.user_id == user.id).all()]
    if not codes:
        return []
    signals = (
        db.query(Signal)
        .filter(Signal.code.in_(codes), Signal.trade_date == date.today())
        .order_by(Signal.score.desc())
        .all()
    )
    return [
        {
            "code": s.code, "stock_name": s.stock_name, "score": s.score,
            "reason": s.reason, "direction": s.direction,
        }
        for s in signals
    ]
