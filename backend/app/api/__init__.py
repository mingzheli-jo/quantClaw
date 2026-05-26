from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.dashboard import router as dashboard_router
from app.api.learn import router as learn_router
from app.api.position import router as position_router
from app.api.scan import router as scan_router
from app.api.settings import router as settings_router
from app.api.signal import router as signal_router
from app.api.stock import router as stock_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(dashboard_router)
api_router.include_router(scan_router)
api_router.include_router(stock_router)
api_router.include_router(position_router)
api_router.include_router(signal_router)
api_router.include_router(settings_router)
api_router.include_router(learn_router)
