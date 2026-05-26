from datetime import date

from sqlalchemy.orm import Session

from app.models.position import Position, TradeLog


def calc_fee(amount: float, action: str) -> float:
    commission = max(amount * 0.00025, 5.0)
    stamp_tax = amount * 0.001 if action == "sell" else 0.0
    return round(commission + stamp_tax, 2)


def open_position(
    db: Session,
    code: str,
    stock_name: str,
    buy_price: float,
    shares: int,
    buy_date: date | None = None,
    stop_loss_pct: float = -0.05,
    take_profit_pct: float = 0.12,
) -> Position:
    if buy_date is None:
        buy_date = date.today()
    cost_amount = buy_price * shares
    pos = Position(
        code=code,
        stock_name=stock_name,
        buy_date=buy_date,
        buy_price=buy_price,
        shares=shares,
        cost_amount=cost_amount,
        stop_loss_price=round(buy_price * (1 + stop_loss_pct), 2),
        take_profit_price=round(buy_price * (1 + take_profit_pct), 2),
        highest_price=buy_price,
        current_price=buy_price,
        status="open",
        executed=True,
    )
    db.add(pos)
    fee = calc_fee(cost_amount, "buy")
    trade = TradeLog(
        code=code,
        stock_name=stock_name,
        trade_date=buy_date,
        action="buy",
        price=buy_price,
        shares=shares,
        amount=cost_amount,
        fee=fee,
        reason="买入建仓",
        position_id=None,
    )
    db.add(trade)
    db.flush()
    trade.position_id = pos.id
    db.commit()
    db.refresh(pos)
    return pos


def close_position(
    db: Session,
    position_id: int,
    close_price: float,
    close_reason: str = "manual",
    close_date: date | None = None,
) -> Position:
    if close_date is None:
        close_date = date.today()
    pos = db.query(Position).get(position_id)
    if pos is None or pos.status != "open":
        raise ValueError("Position not found or already closed")
    amount = close_price * pos.shares
    fee = calc_fee(amount, "sell")
    buy_fee = calc_fee(pos.cost_amount, "buy")
    pnl = (close_price - pos.buy_price) * pos.shares - fee - buy_fee
    pnl_pct = (close_price - pos.buy_price) / pos.buy_price
    pos.status = "closed"
    pos.close_date = close_date
    pos.close_price = close_price
    pos.close_reason = close_reason
    pos.pnl = round(pnl, 2)
    pos.pnl_pct = round(pnl_pct, 4)
    trade = TradeLog(
        code=pos.code,
        stock_name=pos.stock_name,
        trade_date=close_date,
        action="sell",
        price=close_price,
        shares=pos.shares,
        amount=amount,
        fee=fee,
        reason=close_reason,
        position_id=pos.id,
    )
    db.add(trade)
    db.commit()
    db.refresh(pos)
    return pos


def get_active_positions(db: Session) -> list[Position]:
    return db.query(Position).filter(Position.status == "open").all()


def get_position_stats(db: Session) -> dict:
    closed = db.query(Position).filter(Position.status == "closed").all()
    if not closed:
        return {
            "total_trades": 0,
            "win_count": 0,
            "loss_count": 0,
            "win_rate": 0,
            "total_pnl": 0,
            "avg_pnl_pct": 0,
            "avg_hold_days": 0,
        }
    wins = [p for p in closed if (p.pnl or 0) > 0]
    total_pnl = sum(p.pnl or 0 for p in closed)
    avg_pnl_pct = sum(p.pnl_pct or 0 for p in closed) / len(closed)
    avg_hold = sum((p.close_date - p.buy_date).days for p in closed if p.close_date) / len(closed)
    return {
        "total_trades": len(closed),
        "win_count": len(wins),
        "loss_count": len(closed) - len(wins),
        "win_rate": round(len(wins) / len(closed), 4),
        "total_pnl": round(total_pnl, 2),
        "avg_pnl_pct": round(avg_pnl_pct, 4),
        "avg_hold_days": round(avg_hold, 1),
    }
