import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.scheduler.jobs import (
    job_intraday_check,
    job_maintenance,
    job_post_market_analyze,
    job_post_market_collect,
    job_pre_market,
)

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler(timezone="Asia/Shanghai")


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


def start_scheduler():
    scheduler.add_job(job_pre_market, CronTrigger(hour=8, minute=30), id="pre_market", replace_existing=True)
    scheduler.add_job(job_intraday_check, CronTrigger(hour=9, minute=35), id="intraday_0935", replace_existing=True)
    scheduler.add_job(job_intraday_check, CronTrigger(hour=11, minute=35), id="intraday_1135", replace_existing=True)
    scheduler.add_job(
        job_post_market_collect, CronTrigger(hour=15, minute=5), id="post_market_collect", replace_existing=True
    )
    scheduler.add_job(
        job_post_market_analyze, CronTrigger(hour=15, minute=30), id="post_market_analyze", replace_existing=True
    )
    scheduler.add_job(job_maintenance, CronTrigger(hour=20, minute=0), id="maintenance", replace_existing=True)
    scheduler.add_job(
        _job_realtime_refresh, IntervalTrigger(seconds=60),
        id="realtime_refresh", replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started with 7 trading-day jobs")


def shutdown_scheduler():
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")
