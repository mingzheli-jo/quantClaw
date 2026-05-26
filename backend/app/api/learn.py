from datetime import date

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.learn.indicators import INDICATOR_GUIDES
from app.models.system import User

router = APIRouter(prefix="/api/learn", tags=["learn"])


@router.get("/today")
def today_lesson(user: User = Depends(get_current_user)):
    day_of_year = date.today().timetuple().tm_yday
    idx = day_of_year % len(INDICATOR_GUIDES)
    return INDICATOR_GUIDES[idx]


@router.get("/archive")
def archive(user: User = Depends(get_current_user)):
    return INDICATOR_GUIDES
