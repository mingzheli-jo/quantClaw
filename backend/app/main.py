from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import api_router
from app.config import settings
from app.database import Base, engine, SessionLocal
from app.models.system import User
from app.scheduler.setup import start_scheduler, shutdown_scheduler
from app.utils.security import hash_password
import app.models  # noqa: F401


def _seed_admin():
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.username == settings.admin_username).first():
            db.add(User(username=settings.admin_username, hashed_password=hash_password(settings.admin_password)))
            db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _seed_admin()
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
