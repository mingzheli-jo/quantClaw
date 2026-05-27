import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.scheduler.jobs import (
    job_ai_analysis,
    job_intraday_check,
    job_maintenance,
    job_post_market_analyze,
    job_post_market_collect,
    job_pre_market,
)

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler(timezone="Asia/Shanghai")

_JOB_FUNC_MAP = {
    "pre_market": job_pre_market,
    "intraday_0935": job_intraday_check,
    "intraday_1135": job_intraday_check,
    "post_market_collect": job_post_market_collect,
    "post_market_analyze": job_post_market_analyze,
    "ai_analysis": job_ai_analysis,
    "maintenance": job_maintenance,
    "realtime_refresh": None,
}

_DEFAULT_SCHEDULES = {
    "pre_market": {"type": "cron", "hour": 8, "minute": 30},
    "intraday_0935": {"type": "cron", "hour": 9, "minute": 35},
    "intraday_1135": {"type": "cron", "hour": 11, "minute": 35},
    "post_market_collect": {"type": "cron", "hour": 15, "minute": 5},
    "post_market_analyze": {"type": "cron", "hour": 15, "minute": 30},
    "ai_analysis": {"type": "cron", "hour": 15, "minute": 40},
    "maintenance": {"type": "cron", "hour": 20, "minute": 0},
    "realtime_refresh": {"type": "interval", "seconds": 60},
}


def _job_realtime_refresh():
    from app.services.data.realtime import realtime_service
    from app.database import SessionLocal
    from app.models.position import Position
    db = SessionLocal()
    try:
        codes = [p.code for p in db.query(Position).filter(Position.status == "open").all()]
    finally:
        db.close()
    realtime_service.refresh_all(position_codes=codes)


def _get_schedules_from_db() -> dict:
    try:
        from app.database import SessionLocal
        from app.models.job_schedule import JobSchedule
        db = SessionLocal()
        try:
            jobs = db.query(JobSchedule).all()
            if not jobs:
                return {}
            return {
                j.job_id: {
                    "type": j.schedule_type,
                    "hour": j.hour,
                    "minute": j.minute,
                    "seconds": j.interval_seconds,
                    "enabled": j.enabled,
                }
                for j in jobs
            }
        finally:
            db.close()
    except Exception:
        return {}


def _add_job(job_id: str, schedule: dict):
    func = _JOB_FUNC_MAP.get(job_id)
    if job_id == "realtime_refresh":
        func = _job_realtime_refresh
    if not func:
        return
    if not schedule.get("enabled", True):
        try:
            scheduler.remove_job(job_id)
        except Exception:
            pass
        return
    if schedule["type"] == "cron":
        trigger = CronTrigger(hour=schedule["hour"], minute=schedule["minute"])
    else:
        trigger = IntervalTrigger(seconds=schedule.get("seconds", 60))
    scheduler.add_job(func, trigger, id=job_id, replace_existing=True)


def reload_job(job_id: str):
    db_schedules = _get_schedules_from_db()
    if job_id in db_schedules:
        _add_job(job_id, db_schedules[job_id])
        logger.info(f"Reloaded job: {job_id}")
    elif job_id in _DEFAULT_SCHEDULES:
        _add_job(job_id, {**_DEFAULT_SCHEDULES[job_id], "enabled": True})


def start_scheduler():
    db_schedules = _get_schedules_from_db()
    for job_id, default in _DEFAULT_SCHEDULES.items():
        schedule = db_schedules.get(job_id, {**default, "enabled": True})
        _add_job(job_id, schedule)
    scheduler.start()
    logger.info(f"Scheduler started with {len(_DEFAULT_SCHEDULES)} jobs (DB overrides applied)")


def shutdown_scheduler():
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")
