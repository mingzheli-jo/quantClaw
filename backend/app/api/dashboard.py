from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.market import MarketSentiment, NorthFlow
from app.models.position import Position
from app.models.signal import Signal
from app.models.system import User
from app.schemas.dashboard import DashboardOverview, SentimentData

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _calc_temperature(sentiment: MarketSentiment | None, north_net: float = 0) -> int:
    if sentiment is None:
        return 50
    total = sentiment.up_count + sentiment.down_count + sentiment.flat_count
    if total == 0:
        return 50
    up_ratio = sentiment.up_count / total * 40
    limit_score = min(sentiment.limit_up / max(sentiment.limit_down, 1), 5) * 8
    north_score = min(max(north_net / 5e9, -1), 1) * 10 + 10
    return int(min(max(up_ratio + limit_score + north_score, 0), 100))


@router.get("/overview", response_model=DashboardOverview)
def overview(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    today = date.today()
    sentiment = db.query(MarketSentiment).filter(MarketSentiment.trade_date == today).first()
    north = db.query(NorthFlow).filter(NorthFlow.trade_date == today).first()
    north_net = north.net_amount if north else 0
    active = db.query(Position).filter(Position.status == "open").count()
    closed = db.query(Position).filter(Position.status == "closed").all()
    total_pnl = sum(p.pnl or 0 for p in closed)
    week_ago = today - timedelta(days=7)
    recent_signals = db.query(Signal).filter(
        Signal.trade_date >= week_ago, Signal.direction == "buy"
    ).all()
    accuracy = 0.0
    if recent_signals:
        correct = sum(1 for s in recent_signals if s.score >= 65)
        accuracy = correct / len(recent_signals)
    temp = _calc_temperature(sentiment, north_net)
    return DashboardOverview(
        temperature=temp,
        sh_index_pct=sentiment.sh_index_pct if sentiment else 0,
        sz_index_pct=sentiment.sz_index_pct if sentiment else 0,
        cyb_index_pct=sentiment.cyb_index_pct if sentiment else 0,
        limit_up=sentiment.limit_up if sentiment else 0,
        limit_down=sentiment.limit_down if sentiment else 0,
        north_net=north_net,
        active_positions=active,
        total_pnl=total_pnl,
        signal_accuracy_7d=accuracy,
    )


@router.get("/sentiment", response_model=SentimentData)
def sentiment(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = db.query(MarketSentiment).order_by(MarketSentiment.trade_date.desc()).first()
    north = db.query(NorthFlow).order_by(NorthFlow.trade_date.desc()).first()
    if s is None:
        return SentimentData(up_count=0, down_count=0, limit_up=0, limit_down=0, temperature=50)
    temp = _calc_temperature(s, north.net_amount if north else 0)
    return SentimentData(
        up_count=s.up_count,
        down_count=s.down_count,
        limit_up=s.limit_up,
        limit_down=s.limit_down,
        temperature=temp,
    )
