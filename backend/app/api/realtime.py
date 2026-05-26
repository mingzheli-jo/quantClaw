from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.position import Position
from app.models.system import User
from app.services.data.realtime import realtime_service

router = APIRouter(prefix="/api/realtime", tags=["realtime"])


@router.get("/indices")
def get_indices(user: User = Depends(get_current_user)):
    return realtime_service.get_indices()


@router.get("/north-flow")
def get_north_flow(user: User = Depends(get_current_user)):
    return realtime_service.get_north_flow()


@router.get("/sectors")
def get_sectors(user: User = Depends(get_current_user)):
    return realtime_service.get_sectors()


@router.get("/positions")
def get_positions(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    open_positions = db.query(Position).filter(Position.status == "open").all()
    live_prices = {p["code"]: p for p in realtime_service.get_positions()}
    result = []
    for pos in open_positions:
        live = live_prices.get(pos.code, {})
        current_price = live.get("price", pos.current_price or pos.buy_price)
        pnl = (current_price - pos.buy_price) * pos.shares
        pnl_pct = (current_price - pos.buy_price) / pos.buy_price * 100 if pos.buy_price else 0
        result.append({
            "code": pos.code,
            "stock_name": pos.stock_name,
            "buy_price": pos.buy_price,
            "current_price": current_price,
            "change_pct": live.get("change_pct", 0),
            "shares": pos.shares,
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "buy_date": pos.buy_date.isoformat() if pos.buy_date else None,
        })
    return result


@router.get("/summary")
def get_summary(user: User = Depends(get_current_user)):
    return realtime_service.get_summary()
