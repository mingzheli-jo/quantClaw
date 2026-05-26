from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.market import NorthFlow, SectorDaily
from app.models.signal import Signal
from app.models.system import User

router = APIRouter(prefix="/api/scan", tags=["scan"])


@router.get("/ranking")
def ranking(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    today = date.today()
    query = db.query(Signal).filter(
        Signal.trade_date == today, Signal.direction == "buy"
    ).order_by(Signal.score.desc())
    total = query.count()
    items = query.offset((page - 1) * size).limit(size).all()
    return {
        "total": total,
        "page": page,
        "items": [
            {
                "code": s.code,
                "stock_name": s.stock_name,
                "score": s.score,
                "tech_score": s.tech_score,
                "fund_score": s.fund_score,
                "momentum_score": s.momentum_score,
                "sentiment_score": s.sentiment_score,
                "reason": s.reason,
                "close_price": s.close_price,
            }
            for s in items
        ],
    }


@router.get("/sectors")
def sectors(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    today = date.today()
    items = (
        db.query(SectorDaily)
        .filter(SectorDaily.trade_date == today)
        .order_by(SectorDaily.change_pct.desc())
        .all()
    )
    return [
        {"sector": s.sector, "change_pct": s.change_pct, "net_fund_flow": s.net_fund_flow}
        for s in items
    ]


@router.get("/north-flow")
def north_flow(
    days: int = Query(30, ge=1, le=250),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = db.query(NorthFlow).order_by(NorthFlow.trade_date.desc()).limit(days).all()
    items.reverse()
    return [{"trade_date": str(n.trade_date), "net_amount": n.net_amount} for n in items]
