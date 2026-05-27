from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.config import settings as app_settings
from app.models.system import StrategyConfig, User
from app.models.job_schedule import JobSchedule
from app.schemas.settings import DataSourceSettings, NotifySettings, NotifyTestRequest, StrategySettings
from app.services.data.providers.base import DataSourceManager
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


@router.get("/data-source", response_model=DataSourceSettings)
def get_data_source(user: User = Depends(get_current_user)):
    return DataSourceSettings(
        source=DataSourceManager.get_source_name(),
        available=DataSourceManager.available_sources(),
    )


@router.put("/data-source", response_model=DataSourceSettings)
def set_data_source(body: DataSourceSettings, user: User = Depends(get_current_user)):
    DataSourceManager.set_source(body.source)
    return DataSourceSettings(
        source=DataSourceManager.get_source_name(),
        available=DataSourceManager.available_sources(),
    )


DEFAULT_SCHEDULES = [
    {"job_id": "pre_market", "label": "盘前提醒", "schedule_type": "cron", "hour": 8, "minute": 30, "enabled": True},
    {"job_id": "intraday_0935", "label": "盘中检查(早)", "schedule_type": "cron", "hour": 9, "minute": 35, "enabled": True},
    {"job_id": "intraday_1135", "label": "盘中检查(午)", "schedule_type": "cron", "hour": 11, "minute": 35, "enabled": True},
    {"job_id": "post_market_collect", "label": "盘后采集", "schedule_type": "cron", "hour": 15, "minute": 5, "enabled": True},
    {"job_id": "post_market_analyze", "label": "盘后分析", "schedule_type": "cron", "hour": 15, "minute": 30, "enabled": True},
    {"job_id": "ai_analysis", "label": "AI 分析", "schedule_type": "cron", "hour": 15, "minute": 40, "enabled": True},
    {"job_id": "maintenance", "label": "数据维护", "schedule_type": "cron", "hour": 20, "minute": 0, "enabled": True},
    {"job_id": "realtime_refresh", "label": "实时刷新", "schedule_type": "interval", "interval_seconds": 60, "enabled": True},
]


@router.get("/schedules")
def get_schedules(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    existing = db.query(JobSchedule).all()
    if not existing:
        for s in DEFAULT_SCHEDULES:
            db.add(JobSchedule(**s))
        db.commit()
        existing = db.query(JobSchedule).all()
    return [
        {
            "job_id": j.job_id,
            "label": j.label,
            "schedule_type": j.schedule_type,
            "hour": j.hour,
            "minute": j.minute,
            "interval_seconds": j.interval_seconds,
            "enabled": j.enabled,
        }
        for j in existing
    ]


@router.put("/schedules/{job_id}")
def update_schedule(
    job_id: str,
    body: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = db.query(JobSchedule).filter(JobSchedule.job_id == job_id).first()
    if not job:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    if "hour" in body and body["hour"] is not None:
        job.hour = body["hour"]
    if "minute" in body and body["minute"] is not None:
        job.minute = body["minute"]
    if "interval_seconds" in body and body["interval_seconds"] is not None:
        job.interval_seconds = body["interval_seconds"]
    if "enabled" in body:
        job.enabled = body["enabled"]
    db.commit()

    from app.scheduler.setup import reload_job
    reload_job(job_id)

    return {
        "job_id": job.job_id,
        "label": job.label,
        "schedule_type": job.schedule_type,
        "hour": job.hour,
        "minute": job.minute,
        "interval_seconds": job.interval_seconds,
        "enabled": job.enabled,
    }
