from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.position import TradeLog
from app.models.system import User
from app.schemas.position import (
    PositionClose,
    PositionCreate,
    PositionItem,
    PositionStats,
    TradeItem,
)
from app.services.position.manager import (
    close_position,
    get_active_positions,
    get_position_stats,
    open_position,
)

router = APIRouter(prefix="/api/position", tags=["position"])


@router.get("/list", response_model=list[PositionItem])
def list_positions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    positions = get_active_positions(db)
    items = []
    for p in positions:
        hold_days = (date.today() - p.buy_date).days
        pnl_pct = (
            ((p.current_price or p.buy_price) - p.buy_price) / p.buy_price
            if p.buy_price > 0
            else 0
        )
        items.append(
            PositionItem(
                id=p.id,
                code=p.code,
                stock_name=p.stock_name,
                buy_date=p.buy_date,
                buy_price=p.buy_price,
                shares=p.shares,
                cost_amount=p.cost_amount,
                current_price=p.current_price,
                highest_price=p.highest_price,
                pnl_pct=round(pnl_pct, 4),
                status=p.status,
                hold_days=hold_days,
                stop_loss_price=p.stop_loss_price,
                take_profit_price=p.take_profit_price,
                executed=p.executed,
            )
        )
    return items


@router.post("/create", response_model=PositionItem)
def create_position(
    body: PositionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    pos = open_position(db, body.code, body.stock_name, body.buy_price, body.shares, body.buy_date)
    hold_days = (date.today() - pos.buy_date).days
    return PositionItem(
        id=pos.id,
        code=pos.code,
        stock_name=pos.stock_name,
        buy_date=pos.buy_date,
        buy_price=pos.buy_price,
        shares=pos.shares,
        cost_amount=pos.cost_amount,
        current_price=pos.current_price,
        highest_price=pos.highest_price,
        pnl_pct=0,
        status=pos.status,
        hold_days=hold_days,
        stop_loss_price=pos.stop_loss_price,
        take_profit_price=pos.take_profit_price,
        executed=pos.executed,
    )


@router.post("/{position_id}/close", response_model=PositionItem)
def close_pos(
    position_id: int,
    body: PositionClose,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        pos = close_position(db, position_id, body.close_price, body.close_reason, body.close_date)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    hold_days = ((pos.close_date or date.today()) - pos.buy_date).days
    return PositionItem(
        id=pos.id,
        code=pos.code,
        stock_name=pos.stock_name,
        buy_date=pos.buy_date,
        buy_price=pos.buy_price,
        shares=pos.shares,
        cost_amount=pos.cost_amount,
        current_price=pos.close_price,
        highest_price=pos.highest_price,
        pnl_pct=pos.pnl_pct or 0,
        status=pos.status,
        hold_days=hold_days,
        stop_loss_price=pos.stop_loss_price,
        take_profit_price=pos.take_profit_price,
        executed=pos.executed,
    )


@router.get("/trades", response_model=list[TradeItem])
def list_trades(
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    trades = db.query(TradeLog).order_by(TradeLog.trade_date.desc()).limit(limit).all()
    return [TradeItem.model_validate(t) for t in trades]


@router.get("/stats", response_model=PositionStats)
def stats(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return PositionStats(**get_position_stats(db))
