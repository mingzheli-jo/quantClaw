from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.system import SchedulerLog, User

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/health")
def health(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    cutoff = date.today() - timedelta(days=7)
    logs = (
        db.query(SchedulerLog)
        .filter(SchedulerLog.started_at >= cutoff)
        .order_by(SchedulerLog.started_at.desc())
        .limit(100)
        .all()
    )
    return {
        "logs": [
            {
                "id": log.id,
                "job_name": log.job_name,
                "status": log.status,
                "message": log.message,
                "records_collected": log.records_collected,
                "details": log.details,
                "error_message": log.error_message,
                "started_at": str(log.started_at) if log.started_at else None,
                "finished_at": str(log.finished_at) if log.finished_at else None,
            }
            for log in logs
        ]
    }


@router.get("/health/summary")
def health_summary(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    last_success = (
        db.query(SchedulerLog)
        .filter(SchedulerLog.status == "success")
        .order_by(SchedulerLog.started_at.desc())
        .first()
    )
    today_logs = (
        db.query(SchedulerLog)
        .filter(SchedulerLog.started_at >= date.today())
        .all()
    )
    today_status = "no_data"
    if today_logs:
        if any(l.status == "failed" for l in today_logs):
            today_status = "failed"
        elif any(l.status == "partial" for l in today_logs):
            today_status = "partial"
        else:
            today_status = "success"
    return {
        "last_success": str(last_success.started_at) if last_success else None,
        "today_status": today_status,
        "today_jobs": len(today_logs),
    }
