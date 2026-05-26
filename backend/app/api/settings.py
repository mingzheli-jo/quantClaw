from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.config import settings as app_settings
from app.models.system import StrategyConfig, User
from app.schemas.settings import NotifySettings, NotifyTestRequest, StrategySettings
from app.services.notify.feishu import FeishuBot

router = APIRouter(prefix="/api/settings", tags=["settings"])

DEFAULT_STRATEGY = {
    "filter": {
        "min_amount_20d": 50_000_000,
        "max_price": 50,
        "min_list_days": 60,
    },
    "score": {
        "tech_weight": 0.4,
        "fund_weight": 0.3,
        "momentum_weight": 0.2,
        "sentiment_weight": 0.1,
        "min_score": 65,
    },
    "position": {
        "max_positions": 2,
        "max_single_pct": 0.5,
        "cash_reserve_pct": 0.1,
    },
    "risk": {
        "stop_loss_pct": -0.05,
        "take_profit_pct": 0.12,
        "trailing_trigger": 0.07,
        "trailing_drawdown": 0.03,
        "max_hold_days": 5,
    },
}


@router.get("/strategy", response_model=StrategySettings)
def get_strategy(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    cfg = db.query(StrategyConfig).first()
    if cfg is None:
        return StrategySettings(**DEFAULT_STRATEGY)
    return StrategySettings(**cfg.config)


@router.put("/strategy", response_model=StrategySettings)
def update_strategy(
    body: StrategySettings,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    cfg = db.query(StrategyConfig).first()
    if cfg is None:
        cfg = StrategyConfig(config=body.model_dump())
        db.add(cfg)
    else:
        cfg.config = body.model_dump()
    db.commit()
    return body


@router.get("/notify", response_model=NotifySettings)
def get_notify(user: User = Depends(get_current_user)):
    return NotifySettings(feishu_webhook_url=app_settings.feishu_webhook_url or "")


@router.post("/notify/test")
def test_notify(body: NotifyTestRequest, user: User = Depends(get_current_user)):
    bot = FeishuBot(app_settings.feishu_webhook_url)
    ok = bot.send_text(body.message)
    return {"success": ok}
