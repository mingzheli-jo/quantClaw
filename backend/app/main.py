from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import api_router
from app.config import settings
from app.database import Base, engine, SessionLocal
from app.models.system import User
from app.models.strategy import StrategyTemplate
from app.scheduler.setup import start_scheduler, shutdown_scheduler
from app.utils.security import hash_password
from app.services.data.providers.base import DataSourceManager
from app.services.data.providers.eastmoney import EastmoneyProvider
from app.services.data.providers.baostock_provider import BaostockProvider
import app.models  # noqa: F401


def _seed_admin():
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.username == settings.admin_username).first():
            db.add(User(username=settings.admin_username, hashed_password=hash_password(settings.admin_password)))
            db.commit()
    finally:
        db.close()


BUILTIN_STRATEGIES = [
    {
        "name": "稳健短线",
        "description": "均衡多因子策略，适合稳健型投资者。技术面为主，兼顾资金面和动量。",
        "filter_config": {"min_amount_20d": 50_000_000, "max_price": 50, "min_list_days": 60, "exclude_bj": True},
        "score_config": {"tech_weight": 0.4, "fund_weight": 0.3, "momentum_weight": 0.2, "sentiment_weight": 0.1, "ma_periods": [5, 10, 20], "macd_enabled": True, "kdj_enabled": True, "bollinger_enabled": True, "volume_ratio_threshold": 1.5},
        "signal_config": {"min_score": 65, "top_n": 3, "concentration_control": True},
        "risk_config": {"stop_loss_pct": -0.05, "take_profit_pct": 0.12, "trailing_trigger": 0.07, "trailing_drawdown": 0.03, "max_hold_days": 5},
        "is_active": True,
    },
    {
        "name": "均线突破",
        "description": "重技术面策略，聚焦均线多头排列和价格突破信号。",
        "filter_config": {"min_amount_20d": 80_000_000, "max_price": 100, "min_list_days": 120, "exclude_bj": True},
        "score_config": {"tech_weight": 0.6, "fund_weight": 0.15, "momentum_weight": 0.2, "sentiment_weight": 0.05, "ma_periods": [5, 10, 20], "macd_enabled": True, "kdj_enabled": False, "bollinger_enabled": True, "volume_ratio_threshold": 1.2},
        "signal_config": {"min_score": 60, "top_n": 3, "concentration_control": True},
        "risk_config": {"stop_loss_pct": -0.07, "take_profit_pct": 0.15, "trailing_trigger": 0.10, "trailing_drawdown": 0.04, "max_hold_days": 7},
        "is_active": False,
    },
    {
        "name": "资金驱动",
        "description": "重资金面策略，追踪北向资金和主力资金流入方向。",
        "filter_config": {"min_amount_20d": 100_000_000, "max_price": 80, "min_list_days": 90, "exclude_bj": True},
        "score_config": {"tech_weight": 0.2, "fund_weight": 0.5, "momentum_weight": 0.15, "sentiment_weight": 0.15, "ma_periods": [5, 10, 20], "macd_enabled": True, "kdj_enabled": True, "bollinger_enabled": False, "volume_ratio_threshold": 1.5},
        "signal_config": {"min_score": 60, "top_n": 3, "concentration_control": True},
        "risk_config": {"stop_loss_pct": -0.05, "take_profit_pct": 0.10, "trailing_trigger": 0.06, "trailing_drawdown": 0.03, "max_hold_days": 5},
        "is_active": False,
    },
    {
        "name": "动量追涨",
        "description": "重动量策略，选择近期强势股，追涨短线机会。",
        "filter_config": {"min_amount_20d": 80_000_000, "max_price": 60, "min_list_days": 60, "exclude_bj": True},
        "score_config": {"tech_weight": 0.25, "fund_weight": 0.15, "momentum_weight": 0.5, "sentiment_weight": 0.1, "ma_periods": [5, 10, 20], "macd_enabled": True, "kdj_enabled": True, "bollinger_enabled": True, "volume_ratio_threshold": 2.0},
        "signal_config": {"min_score": 70, "top_n": 3, "concentration_control": False},
        "risk_config": {"stop_loss_pct": -0.04, "take_profit_pct": 0.08, "trailing_trigger": 0.05, "trailing_drawdown": 0.02, "max_hold_days": 3},
        "is_active": False,
    },
]


def _seed_strategies():
    db = SessionLocal()
    try:
        if db.query(StrategyTemplate).count() == 0:
            for s in BUILTIN_STRATEGIES:
                db.add(StrategyTemplate(**s, is_builtin=True))
            db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _seed_admin()
    _seed_strategies()
    DataSourceManager.register("eastmoney", EastmoneyProvider())
    DataSourceManager.register("baostock", BaostockProvider())
    start_scheduler()
    yield
    shutdown_scheduler()


app = FastAPI(title="QuantClaw", lifespan=lifespan)
app.include_router(api_router)

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")


@app.get("/api/health")
def health():
    return {"status": "ok"}
