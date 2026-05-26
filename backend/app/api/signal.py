from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.signal import Signal
from app.models.system import User
from app.schemas.signal import SignalItem

router = APIRouter(prefix="/api/signal", tags=["signal"])


@router.get("/today", response_model=list[SignalItem])
def today_signals(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = (
        db.query(Signal)
        .filter(Signal.trade_date == date.today())
        .order_by(Signal.score.desc())
        .all()
    )
    return [SignalItem.model_validate(s) for s in items]


@router.get("/history", response_model=list[SignalItem])
def history(
    days: int = Query(30, ge=1, le=250),
    direction: str = Query("buy"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    cutoff = date.today() - timedelta(days=days)
    items = (
        db.query(Signal)
        .filter(Signal.trade_date >= cutoff, Signal.direction == direction)
        .order_by(Signal.trade_date.desc())
        .limit(100)
        .all()
    )
    return [SignalItem.model_validate(s) for s in items]
