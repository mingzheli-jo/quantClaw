import json
import logging
from datetime import date

from sqlalchemy.orm import Session

from app.config import settings
from app.models.market import MarketSentiment, NorthFlow, SectorDaily
from app.models.signal import Signal
from app.models.stock import StockBasic, StockDaily
from app.models.position import Position
from app.services.ai.llm_client import LLMClient
from app.services.ai.prompts import build_messages

logger = logging.getLogger(__name__)


def _get_llm_client() -> LLMClient:
    from app.database import SessionLocal
    from app.models.config import SystemConfig

    provider = settings.llm_provider
    deepseek_key = settings.deepseek_api_key
    qwen_key = settings.qwen_api_key

    try:
        db = SessionLocal()
        try:
            for row in db.query(SystemConfig).filter(
                SystemConfig.key.in_(["llm_provider", "deepseek_api_key", "qwen_api_key"])
            ).all():
                if row.key == "llm_provider":
                    provider = row.value
                elif row.key == "deepseek_api_key" and row.value:
                    deepseek_key = row.value
                elif row.key == "qwen_api_key" and row.value:
                    qwen_key = row.value
        finally:
            db.close()
    except Exception:
        pass

    key_map = {"deepseek": deepseek_key, "qwen": qwen_key}
    api_key = key_map.get(provider, deepseek_key)
    return LLMClient(api_key=api_key, provider=provider)


def build_stock_context(db: Session, code: str) -> dict:
    today = date.today()
    stock = db.query(StockBasic).filter(StockBasic.code == code).first()
    signal = db.query(Signal).filter(Signal.code == code).order_by(Signal.trade_date.desc()).first()
    klines = (
        db.query(StockDaily)
        .filter(StockDaily.code == code)
        .order_by(StockDaily.trade_date.desc())
        .limit(5)
        .all()
    )
    klines.reverse()
    sentiment = db.query(MarketSentiment).filter(MarketSentiment.trade_date == today).first()
    north = db.query(NorthFlow).order_by(NorthFlow.trade_date.desc()).first()
    industry = stock.industry if stock else ""
    sector = db.query(SectorDaily).filter(
        SectorDaily.sector == industry, SectorDaily.trade_date == today
    ).first()
    position = db.query(Position).filter(
        Position.code == code, Position.status == "open"
    ).first()

    return {
        "code": code,
        "name": stock.name if stock else code,
        "industry": industry,
        "scores": {
            "total": signal.score if signal else 0,
            "tech": signal.tech_score if signal else 0,
            "fund": signal.fund_score if signal else 0,
            "momentum": signal.momentum_score if signal else 0,
            "sentiment": signal.sentiment_score if signal else 0,
        },
        "reason": signal.reason if signal else "",
        "kline_5d": [
            {
                "date": str(k.trade_date),
                "close": k.close,
                "change_pct": k.change_pct or 0,
                "volume": k.volume,
            }
            for k in klines
        ],
        "market": {
            "up_count": sentiment.up_count if sentiment else 0,
            "down_count": sentiment.down_count if sentiment else 0,
            "limit_up": sentiment.limit_up if sentiment else 0,
            "limit_down": sentiment.limit_down if sentiment else 0,
            "north_net": north.net_amount if north else 0,
        },
        "sector_change_pct": sector.change_pct if sector else 0,
        "position": {
            "buy_price": position.buy_price,
            "hold_days": (today - position.buy_date).days,
            "pnl_pct": round(
                (position.current_price - position.buy_price) / position.buy_price * 100, 2
            ) if position.current_price else 0,
        } if position else None,
    }


def analyze_stock(db: Session, code: str) -> dict:
    context = build_stock_context(db, code)
    client = _get_llm_client()
    messages = build_messages(context)
    raw = client.chat(messages)
    if not raw:
        return {"summary": "AI 分析暂时不可用", "risk": "", "suggestion": "", "market_comment": "", "raw": ""}
    try:
        parsed = json.loads(raw)
        return {
            "summary": parsed.get("summary", ""),
            "risk": parsed.get("risk", ""),
            "suggestion": parsed.get("suggestion", ""),
            "market_comment": parsed.get("market_comment", ""),
            "raw": raw,
        }
    except json.JSONDecodeError:
        return {"summary": raw, "risk": "", "suggestion": "", "market_comment": "", "raw": raw}
