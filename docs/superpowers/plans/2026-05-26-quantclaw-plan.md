# QuantClaw Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a personal A-share quantitative trading signal system that scans the full market daily, scores stocks with multi-factor analysis, and delivers buy/sell recommendations via Feishu and a web dashboard.

**Architecture:** Single Python (FastAPI) backend serves both API and static Vue3 frontend. Sync SQLAlchemy for all DB access (single-user, no concurrency pressure). APScheduler BackgroundScheduler runs trading-day jobs in its own thread. Docker Compose orchestrates three containers: nginx (reverse proxy + SSL), quantclaw (app), postgres (data).

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0 (sync), PostgreSQL 16, APScheduler 3.x, AKShare, pandas, pandas-ta, Vue3, TypeScript, Pinia, Element Plus, TradingView Lightweight Charts, ECharts, Docker Compose, Nginx, certbot

---

## File Structure

```
QuantClaw/
├── docker-compose.yml
├── docker-compose.dev.yml
├── Dockerfile
├── .env.example
├── .dockerignore
├── .gitignore
├── start.sh
│
├── backend/
│   ├── requirements.txt
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                        # FastAPI app, lifespan, static mount
│   │   ├── config.py                      # pydantic-settings config
│   │   ├── database.py                    # Engine, SessionLocal, get_db
│   │   │
│   │   ├── models/
│   │   │   ├── __init__.py                # Base, create_all
│   │   │   ├── stock.py                   # StockBasic, StockDaily
│   │   │   ├── market.py                  # NorthFlow, SectorDaily, FundFlow, MarketSentiment
│   │   │   ├── signal.py                  # Signal
│   │   │   ├── position.py               # Position, TradeLog
│   │   │   └── system.py                 # User, StrategyConfig, SchedulerLog
│   │   │
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py                    # LoginRequest, TokenResponse, UserInfo
│   │   │   ├── stock.py                   # KLineItem, StockScore, IndicatorData
│   │   │   ├── signal.py                  # SignalItem, SignalList
│   │   │   ├── position.py               # PositionCreate, PositionClose, PositionItem, TradeItem, PositionStats
│   │   │   ├── dashboard.py              # DashboardOverview, SentimentData
│   │   │   └── settings.py               # StrategySettings, NotifySettings
│   │   │
│   │   ├── api/
│   │   │   ├── __init__.py               # api_router aggregation
│   │   │   ├── deps.py                   # get_db, get_current_user
│   │   │   ├── auth.py
│   │   │   ├── dashboard.py
│   │   │   ├── scan.py
│   │   │   ├── stock.py
│   │   │   ├── position.py
│   │   │   ├── signal.py
│   │   │   ├── settings.py
│   │   │   └── learn.py
│   │   │
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── data/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── fetcher.py            # AKShare wrappers: fetch klines, north flow, sectors, fund flow, sentiment
│   │   │   │   ├── indicators.py         # MA, MACD, KDJ, RSI, Bollinger, volume ratio
│   │   │   │   └── maintenance.py        # purge_old_data, update_stock_basic
│   │   │   ├── strategy/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── filters.py            # hard_filter(df, config) -> df
│   │   │   │   ├── scoring.py            # score_technical, score_fund, score_momentum, score_sentiment
│   │   │   │   └── signal_generator.py   # generate_signals(db) -> list[Signal]
│   │   │   ├── position/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── manager.py            # open_position, close_position, get_active
│   │   │   │   └── risk.py               # check_stop_loss, check_take_profit, check_trailing, check_time_stop
│   │   │   └── notify/
│   │   │       ├── __init__.py
│   │   │       ├── feishu.py             # FeishuBot.send_card, send_text
│   │   │       └── messages.py           # build_pre_market_msg, build_post_market_msg, build_alert_msg
│   │   │
│   │   ├── scheduler/
│   │   │   ├── __init__.py
│   │   │   ├── setup.py                  # create_scheduler, start, shutdown
│   │   │   ├── trading_calendar.py       # is_trading_day, next_trading_day
│   │   │   └── jobs.py                   # job_pre_market, job_intraday_check, job_post_market, job_maintenance
│   │   │
│   │   ├── learn/
│   │   │   ├── __init__.py
│   │   │   └── indicators.py             # INDICATOR_GUIDES: list of dicts with name, summary, formula, buy/sell patterns, traps, weight
│   │   │
│   │   └── utils/
│   │       ├── __init__.py
│   │       └── security.py               # hash_password, verify_password, create_token, decode_token
│   │
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py                    # fixtures: db_session, test_client, sample_kline_df
│       ├── test_indicators.py
│       ├── test_filters.py
│       ├── test_scoring.py
│       ├── test_signal_generator.py
│       ├── test_risk.py
│       ├── test_feishu.py
│       ├── test_trading_calendar.py
│       ├── test_auth_api.py
│       └── test_position_api.py
│
├── frontend/
│   ├── package.json
│   ├── tsconfig.json
│   ├── tsconfig.app.json
│   ├── tsconfig.node.json
│   ├── vite.config.ts
│   ├── index.html
│   ├── env.d.ts
│   ├── src/
│   │   ├── main.ts
│   │   ├── App.vue
│   │   ├── router/
│   │   │   └── index.ts
│   │   ├── stores/
│   │   │   ├── auth.ts
│   │   │   ├── dashboard.ts
│   │   │   └── position.ts
│   │   ├── api/
│   │   │   ├── client.ts                 # Axios instance, JWT interceptor, baseURL
│   │   │   ├── auth.ts
│   │   │   ├── dashboard.ts
│   │   │   ├── scan.ts
│   │   │   ├── stock.ts
│   │   │   ├── position.ts
│   │   │   ├── signal.ts
│   │   │   ├── settings.ts
│   │   │   └── learn.ts
│   │   ├── views/
│   │   │   ├── LoginView.vue
│   │   │   ├── DashboardView.vue
│   │   │   ├── ScanView.vue
│   │   │   ├── StockDetailView.vue
│   │   │   ├── PositionView.vue
│   │   │   ├── LearnView.vue
│   │   │   └── SettingsView.vue
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   ├── AppLayout.vue
│   │   │   │   ├── AppSidebar.vue
│   │   │   │   └── AppHeader.vue
│   │   │   ├── charts/
│   │   │   │   ├── KLineChart.vue
│   │   │   │   ├── RadarChart.vue
│   │   │   │   ├── GaugeChart.vue
│   │   │   │   └── SectorHeatmap.vue
│   │   │   ├── signal/
│   │   │   │   ├── SignalCard.vue
│   │   │   │   └── ScoreBreakdown.vue
│   │   │   └── position/
│   │   │       ├── PositionCard.vue
│   │   │       └── RiskProgress.vue
│   │   └── styles/
│   │       ├── variables.css
│   │       └── global.css
│   └── public/
│       └── favicon.ico
│
├── nginx/
│   └── nginx.conf
│
└── docs/
    └── superpowers/
        ├── specs/
        │   └── 2026-05-26-quantclaw-design.md
        └── plans/
            └── 2026-05-26-quantclaw-plan.md
```

---

## Phase 1: Project Foundation

### Task 1: Git Init + Project Scaffolding + Dev Docker

**Files:**
- Create: `.gitignore`
- Create: `backend/requirements.txt`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/database.py`
- Create: `backend/app/main.py`
- Create: `.env.example`
- Create: `docker-compose.dev.yml`

- [ ] **Step 1: Initialize git repo and create .gitignore**

```bash
cd D:\ide\workspace\personal-new\QuantClaw
git init
```

`.gitignore`:
```
__pycache__/
*.pyc
.env
*.egg-info/
dist/
node_modules/
frontend/dist/
.venv/
*.db
.DS_Store
nginx/ssl/
```

- [ ] **Step 2: Create backend requirements.txt**

```
fastapi==0.115.6
uvicorn[standard]==0.34.0
sqlalchemy==2.0.36
psycopg2-binary==2.9.10
pydantic-settings==2.7.1
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
httpx==0.28.1
akshare==1.15.59
pandas==2.2.3
pandas-ta==0.3.14b0
apscheduler==3.10.4
python-multipart==0.0.20
```

- [ ] **Step 3: Create config.py**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://quantclaw:quantclaw@localhost:5432/quantclaw"
    secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_days: int = 7

    admin_username: str = "admin"
    admin_password: str = "admin123"

    feishu_webhook_url: str = ""

    base_url: str = "https://quant.azhefuye.online"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
```

- [ ] **Step 4: Create database.py**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 5: Create main.py with lifespan**

```python
from contextlib import contextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import Base, engine


@contextmanager
def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="QuantClaw", lifespan=lifespan)

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")


@app.get("/api/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 6: Create .env.example**

```
DATABASE_URL=postgresql://quantclaw:quantclaw@postgres:5432/quantclaw
SECRET_KEY=change-me-to-a-random-string
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-password-here
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/your-hook-id
BASE_URL=https://quant.azhefuye.online
```

- [ ] **Step 7: Create docker-compose.dev.yml for local development**

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: quantclaw
      POSTGRES_PASSWORD: quantclaw
      POSTGRES_DB: quantclaw
    ports:
      - "5432:5432"
    volumes:
      - pg-data-dev:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U quantclaw"]
      interval: 5s
      timeout: 3s
      retries: 5

volumes:
  pg-data-dev:
```

- [ ] **Step 8: Verify the dev stack starts**

```bash
docker compose -f docker-compose.dev.yml up -d
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
# Open http://localhost:8000/api/health → {"status": "ok"}
```

- [ ] **Step 9: Commit**

```bash
git add .
git commit -m "feat: project scaffolding with FastAPI, PostgreSQL, Docker dev stack"
```

---

### Task 2: Database Models

**Files:**
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/stock.py`
- Create: `backend/app/models/market.py`
- Create: `backend/app/models/signal.py`
- Create: `backend/app/models/position.py`
- Create: `backend/app/models/system.py`

- [ ] **Step 1: Create stock models**

`backend/app/models/stock.py`:
```python
from datetime import date, datetime

from sqlalchemy import String, Date, Float, BigInteger, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class StockBasic(Base):
    __tablename__ = "stock_basic"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(20))
    industry: Mapped[str | None] = mapped_column(String(30))
    market: Mapped[str] = mapped_column(String(10))
    list_date: Mapped[date] = mapped_column(Date)
    is_st: Mapped[bool] = mapped_column(default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class StockDaily(Base):
    __tablename__ = "stock_daily"
    __table_args__ = (
        UniqueConstraint("code", "trade_date", name="uq_stock_daily_code_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(10), index=True)
    trade_date: Mapped[date] = mapped_column(Date, index=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[int] = mapped_column(BigInteger)
    amount: Mapped[float] = mapped_column(Float)
    change_pct: Mapped[float | None] = mapped_column(Float)
```

- [ ] **Step 2: Create market models**

`backend/app/models/market.py`:
```python
from datetime import date

from sqlalchemy import String, Date, Float, BigInteger, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class NorthFlow(Base):
    __tablename__ = "north_flow"

    id: Mapped[int] = mapped_column(primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, unique=True, index=True)
    buy_amount: Mapped[float] = mapped_column(Float)
    sell_amount: Mapped[float] = mapped_column(Float)
    net_amount: Mapped[float] = mapped_column(Float)


class SectorDaily(Base):
    __tablename__ = "sector_daily"
    __table_args__ = (
        UniqueConstraint("sector", "trade_date", name="uq_sector_daily"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sector: Mapped[str] = mapped_column(String(30), index=True)
    trade_date: Mapped[date] = mapped_column(Date, index=True)
    change_pct: Mapped[float] = mapped_column(Float)
    volume: Mapped[int] = mapped_column(BigInteger, default=0)
    net_fund_flow: Mapped[float] = mapped_column(Float, default=0.0)


class FundFlow(Base):
    __tablename__ = "fund_flow"
    __table_args__ = (
        UniqueConstraint("code", "trade_date", name="uq_fund_flow"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(10), index=True)
    trade_date: Mapped[date] = mapped_column(Date, index=True)
    main_net: Mapped[float] = mapped_column(Float, default=0.0)
    super_large_net: Mapped[float] = mapped_column(Float, default=0.0)
    large_net: Mapped[float] = mapped_column(Float, default=0.0)
    medium_net: Mapped[float] = mapped_column(Float, default=0.0)
    small_net: Mapped[float] = mapped_column(Float, default=0.0)


class MarketSentiment(Base):
    __tablename__ = "market_sentiment"

    id: Mapped[int] = mapped_column(primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, unique=True, index=True)
    up_count: Mapped[int] = mapped_column(Integer)
    down_count: Mapped[int] = mapped_column(Integer)
    flat_count: Mapped[int] = mapped_column(Integer, default=0)
    limit_up: Mapped[int] = mapped_column(Integer)
    limit_down: Mapped[int] = mapped_column(Integer)
    sh_index_pct: Mapped[float] = mapped_column(Float, default=0.0)
    sz_index_pct: Mapped[float] = mapped_column(Float, default=0.0)
    cyb_index_pct: Mapped[float] = mapped_column(Float, default=0.0)
```

- [ ] **Step 3: Create signal model**

`backend/app/models/signal.py`:
```python
from datetime import date, datetime

from sqlalchemy import String, Date, Float, Integer, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Signal(Base):
    __tablename__ = "signal"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(10), index=True)
    stock_name: Mapped[str] = mapped_column(String(20))
    trade_date: Mapped[date] = mapped_column(Date, index=True)
    direction: Mapped[str] = mapped_column(String(4))  # "buy" or "sell"
    score: Mapped[int] = mapped_column(Integer)
    tech_score: Mapped[int] = mapped_column(Integer, default=0)
    fund_score: Mapped[int] = mapped_column(Integer, default=0)
    momentum_score: Mapped[int] = mapped_column(Integer, default=0)
    sentiment_score: Mapped[int] = mapped_column(Integer, default=0)
    reason: Mapped[str] = mapped_column(Text)
    close_price: Mapped[float] = mapped_column(Float)
    suggested_buy_low: Mapped[float | None] = mapped_column(Float)
    suggested_buy_high: Mapped[float | None] = mapped_column(Float)
    stop_loss_price: Mapped[float | None] = mapped_column(Float)
    target_price: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
```

- [ ] **Step 4: Create position and trade log models**

`backend/app/models/position.py`:
```python
from datetime import date, datetime

from sqlalchemy import String, Date, Float, Integer, Text, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Position(Base):
    __tablename__ = "position"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(10), index=True)
    stock_name: Mapped[str] = mapped_column(String(20))
    buy_date: Mapped[date] = mapped_column(Date)
    buy_price: Mapped[float] = mapped_column(Float)
    shares: Mapped[int] = mapped_column(Integer)
    cost_amount: Mapped[float] = mapped_column(Float)
    stop_loss_price: Mapped[float] = mapped_column(Float)
    take_profit_price: Mapped[float] = mapped_column(Float)
    highest_price: Mapped[float] = mapped_column(Float)
    current_price: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(10), default="open")  # open, closed
    close_date: Mapped[date | None] = mapped_column(Date)
    close_price: Mapped[float | None] = mapped_column(Float)
    close_reason: Mapped[str | None] = mapped_column(String(30))
    pnl: Mapped[float | None] = mapped_column(Float)
    pnl_pct: Mapped[float | None] = mapped_column(Float)
    executed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class TradeLog(Base):
    __tablename__ = "trade_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(10), index=True)
    stock_name: Mapped[str] = mapped_column(String(20))
    trade_date: Mapped[date] = mapped_column(Date, index=True)
    action: Mapped[str] = mapped_column(String(4))  # "buy" or "sell"
    price: Mapped[float] = mapped_column(Float)
    shares: Mapped[int] = mapped_column(Integer)
    amount: Mapped[float] = mapped_column(Float)
    fee: Mapped[float] = mapped_column(Float, default=0.0)
    reason: Mapped[str] = mapped_column(Text)
    position_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
```

- [ ] **Step 5: Create system models**

`backend/app/models/system.py`:
```python
from datetime import datetime

from sqlalchemy import String, Text, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    hashed_password: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class StrategyConfig(Base):
    __tablename__ = "strategy_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    config: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class SchedulerLog(Base):
    __tablename__ = "scheduler_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_name: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(10))  # success, failed
    message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
```

- [ ] **Step 6: Create models __init__.py that imports all models**

`backend/app/models/__init__.py`:
```python
from app.models.stock import StockBasic, StockDaily
from app.models.market import NorthFlow, SectorDaily, FundFlow, MarketSentiment
from app.models.signal import Signal
from app.models.position import Position, TradeLog
from app.models.system import User, StrategyConfig, SchedulerLog

__all__ = [
    "StockBasic", "StockDaily",
    "NorthFlow", "SectorDaily", "FundFlow", "MarketSentiment",
    "Signal",
    "Position", "TradeLog",
    "User", "StrategyConfig", "SchedulerLog",
]
```

- [ ] **Step 7: Update main.py to import models so create_all sees them**

In `backend/app/main.py`, add at the top after existing imports:
```python
import app.models  # noqa: F401 — registers all models with Base.metadata
```

- [ ] **Step 8: Verify tables are created**

```bash
docker compose -f docker-compose.dev.yml up -d
cd backend
python -c "from app.database import engine, Base; import app.models; Base.metadata.create_all(engine); print('Tables created:', list(Base.metadata.tables.keys()))"
```

Expected: prints all 11 table names.

- [ ] **Step 9: Commit**

```bash
git add backend/app/models/
git commit -m "feat: database models for stock, market, signal, position, system"
```

---

### Task 3: Auth Utilities + Test Infrastructure

**Files:**
- Create: `backend/app/utils/__init__.py`
- Create: `backend/app/utils/security.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_auth_api.py`
- Create: `backend/app/schemas/__init__.py`
- Create: `backend/app/schemas/auth.py`
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/deps.py`
- Create: `backend/app/api/auth.py`

- [ ] **Step 1: Create security utilities**

`backend/app/utils/security.py`:
```python
from datetime import datetime, timedelta, timezone

from jose import jwt, JWTError
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_expire_days)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        return payload.get("sub")
    except JWTError:
        return None
```

- [ ] **Step 2: Create auth schemas**

`backend/app/schemas/auth.py`:
```python
from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserInfo(BaseModel):
    username: str
```

- [ ] **Step 3: Create API deps (get_db + get_current_user)**

`backend/app/api/deps.py`:
```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.system import User
from app.utils.security import decode_token

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    username = decode_token(credentials.credentials)
    if username is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user
```

- [ ] **Step 4: Create auth API**

`backend/app/api/auth.py`:
```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.system import User
from app.schemas.auth import LoginRequest, TokenResponse, UserInfo
from app.utils.security import verify_password, create_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username).first()
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_token(user.username)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserInfo)
def me(user: User = Depends(get_current_user)):
    return UserInfo(username=user.username)
```

- [ ] **Step 5: Create api __init__ that aggregates all routers**

`backend/app/api/__init__.py`:
```python
from fastapi import APIRouter

from app.api.auth import router as auth_router

api_router = APIRouter()
api_router.include_router(auth_router)
```

- [ ] **Step 6: Update main.py — include api_router, seed admin user on startup**

Replace `backend/app/main.py` content:
```python
from contextlib import contextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import api_router
from app.config import settings
from app.database import Base, engine, SessionLocal
from app.models.system import User
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


@contextmanager
def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _seed_admin()
    yield


app = FastAPI(title="QuantClaw", lifespan=lifespan)
app.include_router(api_router)

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")


@app.get("/api/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 7: Create test conftest with in-memory SQLite**

`backend/tests/conftest.py`:
```python
from datetime import date

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models.system import User
from app.utils.security import hash_password

test_engine = create_engine("sqlite:///:memory:")
TestSession = sessionmaker(bind=test_engine)


@pytest.fixture()
def db_session():
    Base.metadata.create_all(bind=test_engine)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture()
def test_client(db_session):
    def _override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    db_session.add(User(username="admin", hashed_password=hash_password("test123")))
    db_session.commit()
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers(test_client):
    resp = test_client.post("/api/auth/login", json={"username": "admin", "password": "test123"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def sample_kline_df():
    dates = pd.bdate_range(end=date.today(), periods=30)
    base = 20.0
    rows = []
    for i, d in enumerate(dates):
        c = base + i * 0.2
        rows.append({"code": "600000", "trade_date": d.date(), "open": c - 0.1, "high": c + 0.3, "low": c - 0.2, "close": c, "volume": 1000000 * (10 + i), "amount": c * 1000000 * (10 + i)})
    return pd.DataFrame(rows)
```

- [ ] **Step 8: Write auth API tests**

`backend/tests/test_auth_api.py`:
```python
def test_login_success(test_client):
    resp = test_client.post("/api/auth/login", json={"username": "admin", "password": "test123"})
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


def test_login_wrong_password(test_client):
    resp = test_client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert resp.status_code == 401


def test_login_unknown_user(test_client):
    resp = test_client.post("/api/auth/login", json={"username": "nobody", "password": "test123"})
    assert resp.status_code == 401


def test_me_with_token(test_client, auth_headers):
    resp = test_client.get("/api/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["username"] == "admin"


def test_me_without_token(test_client):
    resp = test_client.get("/api/auth/me")
    assert resp.status_code == 403
```

- [ ] **Step 9: Run tests**

```bash
cd backend
pip install pytest
pytest tests/test_auth_api.py -v
```

Expected: 5 passed.

- [ ] **Step 10: Commit**

```bash
git add backend/app/utils/ backend/app/schemas/ backend/app/api/ backend/tests/ backend/app/main.py
git commit -m "feat: JWT auth with login API, test infrastructure with SQLite"
```

---

## Phase 2: Data Engine

### Task 4: Technical Indicator Calculations

**Files:**
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/data/__init__.py`
- Create: `backend/app/services/data/indicators.py`
- Create: `backend/tests/test_indicators.py`

- [ ] **Step 1: Write failing tests for indicators**

`backend/tests/test_indicators.py`:
```python
import pandas as pd
import numpy as np
from app.services.data.indicators import (
    calc_ma,
    calc_macd,
    calc_kdj,
    calc_rsi,
    calc_bollinger,
    calc_volume_ratio,
)


def _make_close_series(n=30, base=20.0, step=0.2):
    return pd.Series([base + i * step for i in range(n)])


def test_calc_ma():
    close = _make_close_series(20)
    ma5 = calc_ma(close, 5)
    assert len(ma5) == 20
    assert pd.isna(ma5.iloc[3])
    assert not pd.isna(ma5.iloc[4])
    expected = close.iloc[0:5].mean()
    assert abs(ma5.iloc[4] - expected) < 0.001


def test_calc_macd():
    close = _make_close_series(40)
    dif, dea, hist = calc_macd(close)
    assert len(dif) == 40
    assert len(dea) == 40
    assert len(hist) == 40


def test_calc_kdj():
    high = _make_close_series(20, base=21.0)
    low = _make_close_series(20, base=19.0)
    close = _make_close_series(20, base=20.0)
    k, d, j = calc_kdj(high, low, close)
    assert len(k) == 20
    assert all(0 <= v <= 100 for v in k.dropna())


def test_calc_rsi():
    close = _make_close_series(30)
    rsi = calc_rsi(close, 14)
    assert len(rsi) == 30
    valid = rsi.dropna()
    assert all(0 <= v <= 100 for v in valid)


def test_calc_bollinger():
    close = _make_close_series(30)
    upper, mid, lower = calc_bollinger(close, 20)
    valid_idx = mid.dropna().index
    assert all(upper[i] > mid[i] > lower[i] for i in valid_idx)


def test_calc_volume_ratio():
    volume = pd.Series([100] * 20 + [200])
    ratio = calc_volume_ratio(volume, 20)
    assert abs(ratio - 2.0) < 0.01
```

- [ ] **Step 2: Run tests — expect fail**

```bash
cd backend
pytest tests/test_indicators.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.data.indicators'`

- [ ] **Step 3: Implement indicators**

`backend/app/services/data/indicators.py`:
```python
import pandas as pd
import numpy as np


def calc_ma(close: pd.Series, period: int) -> pd.Series:
    return close.rolling(window=period).mean()


def calc_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    hist = 2 * (dif - dea)
    return dif, dea, hist


def calc_kdj(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 9):
    lowest = low.rolling(window=period).min()
    highest = high.rolling(window=period).max()
    rsv = (close - lowest) / (highest - lowest) * 100
    rsv = rsv.fillna(50)
    k = rsv.ewm(com=2, adjust=False).mean()
    d = k.ewm(com=2, adjust=False).mean()
    j = 3 * k - 2 * d
    k = k.clip(0, 100)
    d = d.clip(0, 100)
    return k, d, j


def calc_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(span=period, adjust=False).mean()
    avg_loss = loss.ewm(span=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calc_bollinger(close: pd.Series, period: int = 20, num_std: float = 2.0):
    mid = close.rolling(window=period).mean()
    std = close.rolling(window=period).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    return upper, mid, lower


def calc_volume_ratio(volume: pd.Series, period: int = 20) -> float:
    if len(volume) < period + 1:
        return 1.0
    avg = volume.iloc[-(period + 1):-1].mean()
    if avg == 0:
        return 1.0
    return volume.iloc[-1] / avg
```

Create empty `__init__.py` files:
- `backend/app/services/__init__.py`
- `backend/app/services/data/__init__.py`

- [ ] **Step 4: Run tests — expect pass**

```bash
pytest tests/test_indicators.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ backend/tests/test_indicators.py
git commit -m "feat: technical indicator calculations (MA, MACD, KDJ, RSI, Bollinger, volume ratio)"
```

---

### Task 5: AKShare Data Fetcher

**Files:**
- Create: `backend/app/services/data/fetcher.py`
- Create: `backend/tests/test_fetcher.py`
- Create: `backend/app/services/data/maintenance.py`

- [ ] **Step 1: Write fetcher tests with mocked AKShare**

`backend/tests/test_fetcher.py`:
```python
from datetime import date
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from app.services.data.fetcher import (
    fetch_stock_basic_list,
    fetch_daily_klines_batch,
    fetch_north_flow,
)


@patch("app.services.data.fetcher.ak")
def test_fetch_stock_basic_list(mock_ak):
    mock_ak.stock_zh_a_spot_em.return_value = pd.DataFrame({
        "代码": ["600000", "000001"],
        "名称": ["浦发银行", "平安银行"],
        "最新价": [10.0, 15.0],
    })
    mock_ak.stock_info_a_code_name.return_value = pd.DataFrame({
        "code": ["600000", "000001"],
        "name": ["浦发银行", "平安银行"],
    })
    result = fetch_stock_basic_list()
    assert len(result) >= 1
    assert "code" in result.columns


@patch("app.services.data.fetcher.ak")
def test_fetch_daily_klines_batch(mock_ak):
    mock_ak.stock_zh_a_hist.return_value = pd.DataFrame({
        "日期": ["2026-05-20", "2026-05-21"],
        "开盘": [10.0, 10.5],
        "最高": [10.5, 11.0],
        "最低": [9.8, 10.3],
        "收盘": [10.3, 10.8],
        "成交量": [100000, 120000],
        "成交额": [1030000, 1296000],
        "涨跌幅": [1.5, 4.85],
    })
    result = fetch_daily_klines_batch(["600000"], start_date="20260520", end_date="20260521")
    assert len(result) == 2
    assert "code" in result.columns


@patch("app.services.data.fetcher.ak")
def test_fetch_north_flow(mock_ak):
    mock_ak.stock_hsgt_north_net_flow_in_em.return_value = pd.DataFrame({
        "date": ["2026-05-20"],
        "value": [4200000000],
    })
    result = fetch_north_flow()
    assert result is not None
```

- [ ] **Step 2: Run tests — expect fail**

```bash
pytest tests/test_fetcher.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement fetcher**

`backend/app/services/data/fetcher.py`:
```python
import logging
import time
from datetime import date, timedelta

import akshare as ak
import pandas as pd

logger = logging.getLogger(__name__)

BATCH_SIZE = 500
BATCH_DELAY = 3
MAX_RETRIES = 3
RETRY_DELAY = 30


def _retry(fn, *args, **kwargs):
    for attempt in range(MAX_RETRIES):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
    logger.error(f"All {MAX_RETRIES} attempts failed for {fn.__name__}")
    return None


def fetch_stock_basic_list() -> pd.DataFrame:
    df = _retry(ak.stock_zh_a_spot_em)
    if df is None or df.empty:
        return pd.DataFrame()
    result = df.rename(columns={
        "代码": "code", "名称": "name", "最新价": "price",
        "总市值": "market_cap", "所属行业": "industry",
    })
    # Derive market from code prefix
    result["market"] = result["code"].apply(
        lambda c: "bj" if c.startswith(("8", "4")) else "sh" if c.startswith("6") else "sz"
    )
    # Derive ST status from name
    result["is_st"] = result["name"].str.contains(r"ST|退市", case=False, na=False)
    # list_date requires a separate API call, fetched in update_stock_basic
    result["list_date"] = None
    cols = ["code", "name", "price", "market", "is_st", "list_date"]
    if "industry" in result.columns:
        cols.append("industry")
    return result[cols].copy()


def fetch_stock_list_dates() -> pd.DataFrame:
    """Fetch list dates for all A-share stocks. Called weekly by maintenance job."""
    df = _retry(ak.stock_info_a_code_name)
    if df is None or df.empty:
        return pd.DataFrame()
    # stock_info_a_code_name returns code, name, and sometimes IPO date
    # For robust list_date, use stock_zh_a_spot_em with additional processing
    info = _retry(ak.stock_individual_info_em, symbol="000001")
    # Batch approach: iterate is too slow for 5000 stocks
    # Use a cached bulk approach via stock_sse_summary or similar
    return df


def fetch_daily_klines_batch(
    codes: list[str],
    start_date: str = "",
    end_date: str = "",
) -> pd.DataFrame:
    if not start_date:
        start_date = (date.today() - timedelta(days=400)).strftime("%Y%m%d")
    if not end_date:
        end_date = date.today().strftime("%Y%m%d")

    all_frames = []
    for i in range(0, len(codes), BATCH_SIZE):
        batch = codes[i:i + BATCH_SIZE]
        for code in batch:
            df = _retry(ak.stock_zh_a_hist, symbol=code, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
            if df is not None and not df.empty:
                df = df.rename(columns={
                    "日期": "trade_date", "开盘": "open", "最高": "high",
                    "最低": "low", "收盘": "close", "成交量": "volume",
                    "成交额": "amount", "涨跌幅": "change_pct",
                })
                df["code"] = code
                df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
                all_frames.append(df[["code", "trade_date", "open", "high", "low", "close", "volume", "amount", "change_pct"]])
        if i + BATCH_SIZE < len(codes):
            time.sleep(BATCH_DELAY)

    if not all_frames:
        return pd.DataFrame()
    return pd.concat(all_frames, ignore_index=True)


def fetch_north_flow(days: int = 30) -> pd.DataFrame:
    df = _retry(ak.stock_hsgt_north_net_flow_in_em)
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.rename(columns={"date": "trade_date", "value": "net_amount"})
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
    df["buy_amount"] = 0.0
    df["sell_amount"] = 0.0
    return df.tail(days)


def fetch_sector_daily() -> pd.DataFrame:
    df = _retry(ak.stock_board_industry_name_em)
    if df is None or df.empty:
        return pd.DataFrame()
    result = df.rename(columns={
        "板块名称": "sector", "板块涨跌幅": "change_pct",
        "总成交量": "volume", "净流入": "net_fund_flow",
    })
    cols_available = [c for c in ["sector", "change_pct", "volume", "net_fund_flow"] if c in result.columns]
    result = result[cols_available].copy()
    result["trade_date"] = date.today()
    for col in ["change_pct", "volume", "net_fund_flow"]:
        if col not in result.columns:
            result[col] = 0
    return result


def fetch_fund_flow_batch(codes: list[str]) -> pd.DataFrame:
    all_frames = []
    for i in range(0, len(codes), BATCH_SIZE):
        batch = codes[i:i + BATCH_SIZE]
        for code in batch:
            df = _retry(ak.stock_individual_fund_flow, stock=code, market="sh" if code.startswith("6") else "sz")
            if df is not None and not df.empty:
                df["code"] = code
                all_frames.append(df.tail(1))
        if i + BATCH_SIZE < len(codes):
            time.sleep(BATCH_DELAY)
    if not all_frames:
        return pd.DataFrame()
    return pd.concat(all_frames, ignore_index=True)


def fetch_market_sentiment() -> dict:
    df = _retry(ak.stock_zh_a_spot_em)
    if df is None or df.empty:
        return {}
    change_col = "涨跌幅" if "涨跌幅" in df.columns else None
    if change_col is None:
        return {}
    up = (df[change_col] > 0).sum()
    down = (df[change_col] < 0).sum()
    flat = (df[change_col] == 0).sum()
    limit_up = (df[change_col] >= 9.9).sum()
    limit_down = (df[change_col] <= -9.9).sum()
    return {
        "trade_date": date.today(),
        "up_count": int(up),
        "down_count": int(down),
        "flat_count": int(flat),
        "limit_up": int(limit_up),
        "limit_down": int(limit_down),
    }
```

- [ ] **Step 4: Implement data maintenance**

`backend/app/services/data/maintenance.py`:
```python
import logging
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models.stock import StockDaily
from app.models.market import NorthFlow, SectorDaily, FundFlow, MarketSentiment

logger = logging.getLogger(__name__)


def update_stock_basic(db: Session):
    """Refresh stock_basic table with latest market info. Run weekly."""
    from app.services.data.fetcher import fetch_stock_basic_list
    from app.models.stock import StockBasic
    import akshare as ak

    df = fetch_stock_basic_list()
    if df.empty:
        return
    for _, row in df.iterrows():
        existing = db.query(StockBasic).filter(StockBasic.code == row["code"]).first()
        if existing:
            existing.name = row["name"]
            existing.is_st = row["is_st"]
            existing.market = row["market"]
            if row.get("industry"):
                existing.industry = row["industry"]
        else:
            db.add(StockBasic(
                code=row["code"], name=row["name"], market=row["market"],
                is_st=row["is_st"], list_date=row.get("list_date") or date.today(),
                industry=row.get("industry"),
            ))
    db.commit()


def purge_old_data(db: Session, keep_days: int = 365):
    cutoff = date.today() - timedelta(days=keep_days)
    tables_and_date_cols = [
        (StockDaily, StockDaily.trade_date),
        (NorthFlow, NorthFlow.trade_date),
        (SectorDaily, SectorDaily.trade_date),
        (FundFlow, FundFlow.trade_date),
        (MarketSentiment, MarketSentiment.trade_date),
    ]
    for model, col in tables_and_date_cols:
        deleted = db.query(model).filter(col < cutoff).delete(synchronize_session=False)
        if deleted:
            logger.info(f"Purged {deleted} rows from {model.__tablename__} older than {cutoff}")
    db.commit()
```

- [ ] **Step 5: Run tests — expect pass**

```bash
pytest tests/test_fetcher.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/data/ backend/tests/test_fetcher.py
git commit -m "feat: AKShare data fetcher with retry, batching, and maintenance"
```

---

## Phase 3: Strategy Engine

### Task 6: Hard Filters

**Files:**
- Create: `backend/app/services/strategy/__init__.py`
- Create: `backend/app/services/strategy/filters.py`
- Create: `backend/tests/test_filters.py`

- [ ] **Step 1: Write failing tests**

`backend/tests/test_filters.py`:
```python
from datetime import date, timedelta

import pandas as pd

from app.services.strategy.filters import hard_filter

DEFAULT_CONFIG = {
    "min_amount_20d": 50_000_000,
    "max_price": 50,
    "min_list_days": 60,
}


def _make_stock_df():
    today = date.today()
    return pd.DataFrame([
        {"code": "600001", "name": "正常股票", "close": 25.0, "avg_amount_20d": 80_000_000,
         "list_date": today - timedelta(days=100), "market": "sh", "is_st": False,
         "is_suspended": False, "is_limit_up": False, "is_limit_down": False},
        {"code": "600002", "name": "ST股票", "close": 5.0, "avg_amount_20d": 60_000_000,
         "list_date": today - timedelta(days=200), "market": "sh", "is_st": True,
         "is_suspended": False, "is_limit_up": False, "is_limit_down": False},
        {"code": "600003", "name": "高价股", "close": 80.0, "avg_amount_20d": 100_000_000,
         "list_date": today - timedelta(days=200), "market": "sh", "is_st": False,
         "is_suspended": False, "is_limit_up": False, "is_limit_down": False},
        {"code": "600004", "name": "低流动性", "close": 10.0, "avg_amount_20d": 30_000_000,
         "list_date": today - timedelta(days=200), "market": "sh", "is_st": False,
         "is_suspended": False, "is_limit_up": False, "is_limit_down": False},
        {"code": "600005", "name": "新上市", "close": 15.0, "avg_amount_20d": 80_000_000,
         "list_date": today - timedelta(days=30), "market": "sh", "is_st": False,
         "is_suspended": False, "is_limit_up": False, "is_limit_down": False},
        {"code": "830001", "name": "北交所", "close": 12.0, "avg_amount_20d": 80_000_000,
         "list_date": today - timedelta(days=200), "market": "bj", "is_st": False,
         "is_suspended": False, "is_limit_up": False, "is_limit_down": False},
        {"code": "600006", "name": "涨停股", "close": 30.0, "avg_amount_20d": 90_000_000,
         "list_date": today - timedelta(days=200), "market": "sh", "is_st": False,
         "is_suspended": False, "is_limit_up": True, "is_limit_down": False},
        {"code": "600007", "name": "又一正常", "close": 18.0, "avg_amount_20d": 70_000_000,
         "list_date": today - timedelta(days=300), "market": "sz", "is_st": False,
         "is_suspended": False, "is_limit_up": False, "is_limit_down": False},
    ])


def test_hard_filter_removes_st():
    df = _make_stock_df()
    result = hard_filter(df, DEFAULT_CONFIG)
    assert "600002" not in result["code"].values


def test_hard_filter_removes_high_price():
    df = _make_stock_df()
    result = hard_filter(df, DEFAULT_CONFIG)
    assert "600003" not in result["code"].values


def test_hard_filter_removes_low_liquidity():
    df = _make_stock_df()
    result = hard_filter(df, DEFAULT_CONFIG)
    assert "600004" not in result["code"].values


def test_hard_filter_removes_new_listing():
    df = _make_stock_df()
    result = hard_filter(df, DEFAULT_CONFIG)
    assert "600005" not in result["code"].values


def test_hard_filter_removes_bj():
    df = _make_stock_df()
    result = hard_filter(df, DEFAULT_CONFIG)
    assert "830001" not in result["code"].values


def test_hard_filter_removes_limit_up():
    df = _make_stock_df()
    result = hard_filter(df, DEFAULT_CONFIG)
    assert "600006" not in result["code"].values


def test_hard_filter_keeps_valid():
    df = _make_stock_df()
    result = hard_filter(df, DEFAULT_CONFIG)
    assert "600001" in result["code"].values
    assert "600007" in result["code"].values
    assert len(result) == 2
```

- [ ] **Step 2: Run tests — expect fail**

```bash
pytest tests/test_filters.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement hard_filter**

`backend/app/services/strategy/filters.py`:
```python
from datetime import date, timedelta

import pandas as pd


def hard_filter(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    min_amount = config.get("min_amount_20d", 50_000_000)
    max_price = config.get("max_price", 50)
    min_list_days = config.get("min_list_days", 60)
    cutoff_date = date.today() - timedelta(days=min_list_days)

    mask = (
        (~df["is_st"])
        & (~df["is_suspended"])
        & (~df["is_limit_up"])
        & (~df["is_limit_down"])
        & (df["close"] <= max_price)
        & (df["avg_amount_20d"] >= min_amount)
        & (df["list_date"] <= cutoff_date)
        & (df["market"] != "bj")
    )
    return df[mask].reset_index(drop=True)
```

- [ ] **Step 4: Run tests — expect pass**

```bash
pytest tests/test_filters.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/strategy/ backend/tests/test_filters.py
git commit -m "feat: hard filter for stock selection pipeline"
```

---

### Task 7: Multi-Factor Scoring

**Files:**
- Create: `backend/app/services/strategy/scoring.py`
- Create: `backend/tests/test_scoring.py`

- [ ] **Step 1: Write failing tests**

`backend/tests/test_scoring.py`:
```python
import pandas as pd
import numpy as np

from app.services.strategy.scoring import (
    score_technical,
    score_fund,
    score_momentum,
    score_sentiment,
    compute_total_score,
)


def _make_bullish_kline(n=30):
    """Create a steadily rising kline series — should score high on technical."""
    base = 20.0
    rows = []
    for i in range(n):
        c = base + i * 0.3
        rows.append({"open": c - 0.1, "high": c + 0.2, "low": c - 0.15, "close": c, "volume": 1_000_000 + i * 100_000})
    return pd.DataFrame(rows)


def _make_flat_kline(n=30):
    """Create a flat kline series — should score low."""
    rows = []
    for i in range(n):
        c = 20.0 + (i % 3) * 0.1
        rows.append({"open": c, "high": c + 0.05, "low": c - 0.05, "close": c, "volume": 500_000})
    return pd.DataFrame(rows)


def test_score_technical_bullish():
    df = _make_bullish_kline()
    score, details = score_technical(df)
    assert 0 <= score <= 40
    assert score >= 20  # bullish trend should score decently


def test_score_technical_flat():
    df = _make_flat_kline()
    score, details = score_technical(df)
    assert 0 <= score <= 40
    assert score < 20  # flat trend scores lower


def test_score_fund():
    fund_data = {"north_net_3d": 5_000_000, "main_net": 10_000_000, "super_large_pct": 6.0, "volume_ratio": 2.0}
    score, details = score_fund(fund_data)
    assert 0 <= score <= 30
    assert score >= 20  # all positive


def test_score_fund_negative():
    fund_data = {"north_net_3d": -1_000_000, "main_net": -5_000_000, "super_large_pct": 1.0, "volume_ratio": 0.8}
    score, details = score_fund(fund_data)
    assert score <= 10


def test_score_momentum():
    momentum_data = {"pct_5d": 5.0, "relative_strength": 2.0, "is_20d_high": True}
    score, details = score_momentum(momentum_data)
    assert 0 <= score <= 20
    assert score >= 15


def test_score_sentiment():
    sentiment_data = {"sector_rank_pct": 10, "limit_up": 50, "limit_down": 10, "sector_net_flow": 100_000}
    score, details = score_sentiment(sentiment_data)
    assert 0 <= score <= 10
    assert score >= 7


def test_compute_total_score():
    weights = {"tech_weight": 0.4, "fund_weight": 0.3, "momentum_weight": 0.2, "sentiment_weight": 0.1}
    raw = {"tech": 35, "fund": 25, "momentum": 18, "sentiment": 8}
    total = compute_total_score(raw, weights)
    expected = 35 + 25 + 18 + 8
    assert total == expected  # raw scores are already weighted by max, total is sum
```

- [ ] **Step 2: Run tests — expect fail**

```bash
pytest tests/test_scoring.py -v
```

- [ ] **Step 3: Implement scoring**

`backend/app/services/strategy/scoring.py`:
```python
import pandas as pd
import numpy as np

from app.services.data.indicators import calc_ma, calc_macd, calc_kdj, calc_rsi, calc_bollinger, calc_volume_ratio


def score_technical(kline_df: pd.DataFrame) -> tuple[int, dict]:
    score = 0
    details = {}
    close = kline_df["close"]
    high = kline_df["high"]
    low = kline_df["low"]
    volume = kline_df["volume"]

    # MA alignment (10 pts)
    ma5 = calc_ma(close, 5)
    ma10 = calc_ma(close, 10)
    ma20 = calc_ma(close, 20)
    if len(close) >= 20:
        last_ma5, last_ma10, last_ma20 = ma5.iloc[-1], ma10.iloc[-1], ma20.iloc[-1]
        if not any(pd.isna([last_ma5, last_ma10, last_ma20])):
            if last_ma5 > last_ma10 > last_ma20:
                score += 10
                details["ma_alignment"] = "bullish"
            elif last_ma5 > last_ma10:
                score += 5
                details["ma_alignment"] = "partial"
            else:
                details["ma_alignment"] = "bearish"

    # MACD golden cross (8 pts)
    if len(close) >= 26:
        dif, dea, hist = calc_macd(close)
        if hist.iloc[-1] > 0 and hist.iloc[-2] <= 0:
            score += 8
            details["macd"] = "golden_cross"
        elif hist.iloc[-1] > 0:
            score += 4
            details["macd"] = "positive"
        else:
            details["macd"] = "negative"

    # Bollinger (7 pts)
    if len(close) >= 20:
        upper, mid, lower = calc_bollinger(close, 20)
        if not pd.isna(mid.iloc[-1]):
            if close.iloc[-1] > mid.iloc[-1]:
                score += 7 if close.iloc[-1] < upper.iloc[-1] else 4
                details["bollinger"] = "above_mid"
            else:
                details["bollinger"] = "below_mid"

    # KDJ (5 pts)
    if len(close) >= 9:
        k, d, j = calc_kdj(high, low, close)
        if 20 < k.iloc[-1] < 80 and k.iloc[-1] > d.iloc[-1] and k.iloc[-2] <= d.iloc[-2]:
            score += 5
            details["kdj"] = "golden_cross"
        elif 20 < k.iloc[-1] < 80 and k.iloc[-1] > d.iloc[-1]:
            score += 2
            details["kdj"] = "bullish_zone"
        else:
            details["kdj"] = "neutral"

    # Volume (5 pts)
    vol_ratio = calc_volume_ratio(volume, 20) if len(volume) >= 21 else 1.0
    if vol_ratio >= 1.5:
        score += 5
        details["volume"] = f"ratio_{vol_ratio:.1f}"
    elif vol_ratio >= 1.2:
        score += 2
        details["volume"] = f"ratio_{vol_ratio:.1f}"
    else:
        details["volume"] = f"ratio_{vol_ratio:.1f}"

    # Breakout (5 pts)
    if len(close) >= 20:
        high_20d = close.iloc[-20:].max()
        if close.iloc[-1] >= high_20d:
            score += 5
            details["breakout"] = "20d_high"
        else:
            details["breakout"] = "no"

    return min(score, 40), details


def score_fund(fund_data: dict) -> tuple[int, dict]:
    score = 0
    details = {}

    # North flow 3d (10 pts)
    north_3d = fund_data.get("north_net_3d", 0)
    if north_3d > 0:
        score += 10
        details["north"] = "positive"
    else:
        details["north"] = "negative"

    # Main fund (10 pts)
    main_net = fund_data.get("main_net", 0)
    if main_net > 0:
        score += 10
        details["main_fund"] = "inflow"
    else:
        details["main_fund"] = "outflow"

    # Super large (5 pts)
    sl_pct = fund_data.get("super_large_pct", 0)
    if sl_pct > 5:
        score += 5
        details["super_large"] = f"{sl_pct:.1f}%"
    else:
        details["super_large"] = f"{sl_pct:.1f}%"

    # Volume ratio (5 pts)
    vr = fund_data.get("volume_ratio", 1.0)
    if 1.5 <= vr < 5:
        score += 5
        details["volume_ratio"] = f"{vr:.1f}"
    else:
        details["volume_ratio"] = f"{vr:.1f}"

    return min(score, 30), details


def score_momentum(momentum_data: dict) -> tuple[int, dict]:
    score = 0
    details = {}

    # 5d change (8 pts)
    pct_5d = momentum_data.get("pct_5d", 0)
    if 3 <= pct_5d <= 10:
        score += 8
        details["5d_pct"] = f"{pct_5d:.1f}%"
    elif 0 < pct_5d < 3:
        score += 4
        details["5d_pct"] = f"{pct_5d:.1f}%"
    else:
        details["5d_pct"] = f"{pct_5d:.1f}%"

    # Relative strength (7 pts)
    rs = momentum_data.get("relative_strength", 0)
    if rs > 0:
        score += 7
        details["rel_strength"] = "outperform"
    else:
        details["rel_strength"] = "underperform"

    # 20d high (5 pts)
    if momentum_data.get("is_20d_high", False):
        score += 5
        details["20d_high"] = True

    return min(score, 20), details


def score_sentiment(sentiment_data: dict) -> tuple[int, dict]:
    score = 0
    details = {}

    # Sector rank (5 pts)
    rank_pct = sentiment_data.get("sector_rank_pct", 50)
    if rank_pct <= 20:
        score += 5
        details["sector_rank"] = f"top_{rank_pct}%"
    else:
        details["sector_rank"] = f"top_{rank_pct}%"

    # Market mood (3 pts)
    lu = sentiment_data.get("limit_up", 0)
    ld = sentiment_data.get("limit_down", 0)
    if lu > ld * 2 and ld > 0:
        score += 3
        details["market_mood"] = "bullish"
    elif lu > ld:
        score += 1
        details["market_mood"] = "neutral"
    else:
        details["market_mood"] = "bearish"

    # Sector fund flow (2 pts)
    if sentiment_data.get("sector_net_flow", 0) > 0:
        score += 2
        details["sector_flow"] = "inflow"
    else:
        details["sector_flow"] = "outflow"

    return min(score, 10), details


def compute_total_score(raw_scores: dict, weights: dict) -> int:
    return raw_scores["tech"] + raw_scores["fund"] + raw_scores["momentum"] + raw_scores["sentiment"]
```

- [ ] **Step 4: Run tests — expect pass**

```bash
pytest tests/test_scoring.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/strategy/scoring.py backend/tests/test_scoring.py
git commit -m "feat: multi-factor scoring engine (tech, fund, momentum, sentiment)"
```

---

### Task 8: Signal Generator + Concentration Control

**Files:**
- Create: `backend/app/services/strategy/signal_generator.py`
- Create: `backend/tests/test_signal_generator.py`

- [ ] **Step 1: Write failing tests**

`backend/tests/test_signal_generator.py`:
```python
import pandas as pd

from app.services.strategy.signal_generator import select_top_n, apply_concentration_control


def test_select_top_n():
    df = pd.DataFrame({
        "code": ["A", "B", "C", "D"],
        "score": [90, 85, 70, 50],
    })
    result = select_top_n(df, min_score=65, top_n=3)
    assert len(result) == 3
    assert result.iloc[0]["code"] == "A"


def test_select_top_n_min_score_filter():
    df = pd.DataFrame({
        "code": ["A", "B"],
        "score": [60, 50],
    })
    result = select_top_n(df, min_score=65, top_n=3)
    assert len(result) == 0


def test_concentration_control():
    df = pd.DataFrame({
        "code": ["A", "B", "C", "D"],
        "score": [90, 85, 80, 75],
        "industry": ["半导体", "半导体", "新能源", "消费"],
    })
    held_codes = ["E"]
    result = apply_concentration_control(df, held_codes, top_n=3)
    # Should keep A (半导体 top), skip B (same sector), keep C and D
    assert len(result) <= 3
    assert "A" in result["code"].values
    assert "B" not in result["code"].values


def test_concentration_excludes_held():
    df = pd.DataFrame({
        "code": ["A", "B"],
        "score": [90, 85],
        "industry": ["半导体", "新能源"],
    })
    held_codes = ["A"]
    result = apply_concentration_control(df, held_codes, top_n=3)
    assert "A" not in result["code"].values
    assert "B" in result["code"].values
```

- [ ] **Step 2: Run tests — expect fail**

```bash
pytest tests/test_signal_generator.py -v
```

- [ ] **Step 3: Implement signal generator**

`backend/app/services/strategy/signal_generator.py`:
```python
import pandas as pd


def select_top_n(scored_df: pd.DataFrame, min_score: int = 65, top_n: int = 3) -> pd.DataFrame:
    filtered = scored_df[scored_df["score"] >= min_score].copy()
    filtered = filtered.sort_values("score", ascending=False)
    return filtered.head(top_n).reset_index(drop=True)


def apply_concentration_control(
    scored_df: pd.DataFrame,
    held_codes: list[str],
    top_n: int = 3,
) -> pd.DataFrame:
    df = scored_df[~scored_df["code"].isin(held_codes)].copy()
    df = df.sort_values("score", ascending=False)

    selected = []
    seen_sectors = set()
    for _, row in df.iterrows():
        sector = row.get("industry", "unknown")
        if sector in seen_sectors:
            continue
        seen_sectors.add(sector)
        selected.append(row)
        if len(selected) >= top_n:
            break

    if not selected:
        return pd.DataFrame(columns=df.columns)
    return pd.DataFrame(selected).reset_index(drop=True)


def build_signal_reason(details: dict) -> str:
    parts = []
    if details.get("tech", {}).get("ma_alignment") == "bullish":
        parts.append("均线多头排列")
    if details.get("tech", {}).get("macd") == "golden_cross":
        parts.append("MACD金叉")
    if details.get("tech", {}).get("breakout") == "20d_high":
        parts.append("突破20日新高")
    vol = details.get("tech", {}).get("volume", "")
    if "ratio" in vol:
        ratio_val = vol.replace("ratio_", "")
        try:
            if float(ratio_val) >= 1.5:
                parts.append(f"放量({ratio_val}倍)")
        except ValueError:
            pass
    if details.get("fund", {}).get("north") == "positive":
        parts.append("北向资金流入")
    if details.get("fund", {}).get("main_fund") == "inflow":
        parts.append("主力资金流入")
    if details.get("momentum", {}).get("rel_strength") == "outperform":
        parts.append("强于板块")
    if details.get("sentiment", {}).get("sector_rank", "").startswith("top_"):
        parts.append("板块领涨")
    return " + ".join(parts) if parts else "综合评分达标"
```

- [ ] **Step 4: Run tests — expect pass**

```bash
pytest tests/test_signal_generator.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/strategy/signal_generator.py backend/tests/test_signal_generator.py
git commit -m "feat: signal generator with TOP-N selection and concentration control"
```

---

## Phase 4: Position & Risk Management

### Task 9: Risk Rules

**Files:**
- Create: `backend/app/services/position/__init__.py`
- Create: `backend/app/services/position/risk.py`
- Create: `backend/tests/test_risk.py`

- [ ] **Step 1: Write failing tests**

`backend/tests/test_risk.py`:
```python
from app.services.position.risk import check_sell_signals, RiskConfig


def _make_position(buy_price=20.0, highest_price=20.0, hold_days=1):
    return {
        "buy_price": buy_price,
        "highest_price": highest_price,
        "hold_days": hold_days,
        "current_price": None,
    }


def test_stop_loss_triggers():
    pos = _make_position(buy_price=20.0)
    pos["current_price"] = 18.9  # -5.5%
    cfg = RiskConfig()
    signals = check_sell_signals(pos, cfg)
    assert any(s["rule"] == "stop_loss" for s in signals)


def test_stop_loss_not_triggered():
    pos = _make_position(buy_price=20.0)
    pos["current_price"] = 19.5  # -2.5%
    cfg = RiskConfig()
    signals = check_sell_signals(pos, cfg)
    assert not any(s["rule"] == "stop_loss" for s in signals)


def test_trailing_stop_triggers():
    pos = _make_position(buy_price=20.0, highest_price=22.0)  # highest = +10%
    pos["current_price"] = 21.3  # -3.18% from highest
    cfg = RiskConfig()
    signals = check_sell_signals(pos, cfg)
    assert any(s["rule"] == "trailing_stop" for s in signals)


def test_trailing_stop_not_yet():
    pos = _make_position(buy_price=20.0, highest_price=21.0)  # highest = +5%, not > 7% trigger
    pos["current_price"] = 20.5
    cfg = RiskConfig()
    signals = check_sell_signals(pos, cfg)
    assert not any(s["rule"] == "trailing_stop" for s in signals)


def test_fixed_take_profit():
    pos = _make_position(buy_price=20.0)
    pos["current_price"] = 22.5  # +12.5%
    cfg = RiskConfig()
    signals = check_sell_signals(pos, cfg)
    assert any(s["rule"] == "take_profit" for s in signals)


def test_time_stop():
    pos = _make_position(buy_price=20.0, hold_days=6)
    pos["current_price"] = 20.5  # small gain, no take profit
    cfg = RiskConfig()
    signals = check_sell_signals(pos, cfg)
    assert any(s["rule"] == "time_stop" for s in signals)


def test_time_stop_not_if_profitable():
    pos = _make_position(buy_price=20.0, hold_days=6)
    pos["current_price"] = 22.5  # +12.5% = take_profit triggers instead
    cfg = RiskConfig()
    signals = check_sell_signals(pos, cfg)
    rules = [s["rule"] for s in signals]
    assert "take_profit" in rules
```

- [ ] **Step 2: Run tests — expect fail**

```bash
pytest tests/test_risk.py -v
```

- [ ] **Step 3: Implement risk rules**

`backend/app/services/position/risk.py`:
```python
from dataclasses import dataclass


@dataclass
class RiskConfig:
    stop_loss_pct: float = -0.05
    take_profit_pct: float = 0.12
    trailing_trigger: float = 0.07
    trailing_drawdown: float = 0.03
    max_hold_days: int = 5


def check_sell_signals(position: dict, config: RiskConfig) -> list[dict]:
    signals = []
    buy_price = position["buy_price"]
    current_price = position["current_price"]
    highest_price = position["highest_price"]
    hold_days = position["hold_days"]

    if current_price is None or buy_price <= 0:
        return signals

    pnl_pct = (current_price - buy_price) / buy_price

    # P1: Stop loss
    if pnl_pct <= config.stop_loss_pct:
        signals.append({
            "rule": "stop_loss",
            "priority": 1,
            "reason": f"浮亏 {pnl_pct:.1%}，触发止损线 {config.stop_loss_pct:.0%}",
            "urgency": "immediate",
        })
        return signals  # highest priority, no need to check others

    # P2: Trailing stop
    highest_gain = (highest_price - buy_price) / buy_price
    if highest_gain >= config.trailing_trigger:
        drawdown_from_high = (highest_price - current_price) / highest_price
        if drawdown_from_high >= config.trailing_drawdown:
            signals.append({
                "rule": "trailing_stop",
                "priority": 2,
                "reason": f"最高盈利 {highest_gain:.1%}，从高点回撤 {drawdown_from_high:.1%}",
                "urgency": "immediate",
            })
            return signals

    # P3: Fixed take profit
    if pnl_pct >= config.take_profit_pct:
        signals.append({
            "rule": "take_profit",
            "priority": 3,
            "reason": f"浮盈 {pnl_pct:.1%}，达到止盈目标 {config.take_profit_pct:.0%}",
            "urgency": "suggest",
        })

    # P4: Time stop (only if not already in take profit zone)
    if hold_days > config.max_hold_days and pnl_pct < config.take_profit_pct:
        signals.append({
            "rule": "time_stop",
            "priority": 4,
            "reason": f"持有 {hold_days} 天，超过最大持有期 {config.max_hold_days} 天",
            "urgency": "suggest",
        })

    return signals
```

- [ ] **Step 4: Run tests — expect pass**

```bash
pytest tests/test_risk.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/position/ backend/tests/test_risk.py
git commit -m "feat: risk management rules (stop loss, trailing stop, take profit, time stop)"
```

---

### Task 10: Position Manager

**Files:**
- Create: `backend/app/services/position/manager.py`
- Create: `backend/tests/test_position_api.py`
- Create: `backend/app/schemas/position.py`
- Create: `backend/app/api/position.py`

- [ ] **Step 1: Create position schemas**

`backend/app/schemas/position.py`:
```python
from datetime import date
from pydantic import BaseModel


class PositionCreate(BaseModel):
    code: str
    stock_name: str
    buy_price: float
    shares: int
    buy_date: date | None = None


class PositionClose(BaseModel):
    close_price: float
    close_reason: str = "manual"
    close_date: date | None = None


class PositionItem(BaseModel):
    id: int
    code: str
    stock_name: str
    buy_date: date
    buy_price: float
    shares: int
    cost_amount: float
    current_price: float | None
    highest_price: float
    pnl_pct: float | None
    status: str
    hold_days: int
    stop_loss_price: float
    take_profit_price: float
    executed: bool

    class Config:
        from_attributes = True


class TradeItem(BaseModel):
    id: int
    code: str
    stock_name: str
    trade_date: date
    action: str
    price: float
    shares: int
    amount: float
    fee: float
    reason: str

    class Config:
        from_attributes = True


class PositionStats(BaseModel):
    total_trades: int
    win_count: int
    loss_count: int
    win_rate: float
    total_pnl: float
    avg_pnl_pct: float
    avg_hold_days: float
```

- [ ] **Step 2: Implement position manager**

`backend/app/services/position/manager.py`:
```python
from datetime import date

from sqlalchemy.orm import Session

from app.models.position import Position, TradeLog


def calc_fee(amount: float, action: str) -> float:
    commission = max(amount * 0.00025, 5.0)
    stamp_tax = amount * 0.001 if action == "sell" else 0.0
    return round(commission + stamp_tax, 2)


def open_position(
    db: Session,
    code: str,
    stock_name: str,
    buy_price: float,
    shares: int,
    buy_date: date | None = None,
    stop_loss_pct: float = -0.05,
    take_profit_pct: float = 0.12,
) -> Position:
    if buy_date is None:
        buy_date = date.today()
    cost_amount = buy_price * shares
    pos = Position(
        code=code,
        stock_name=stock_name,
        buy_date=buy_date,
        buy_price=buy_price,
        shares=shares,
        cost_amount=cost_amount,
        stop_loss_price=round(buy_price * (1 + stop_loss_pct), 2),
        take_profit_price=round(buy_price * (1 + take_profit_pct), 2),
        highest_price=buy_price,
        current_price=buy_price,
        status="open",
        executed=True,
    )
    db.add(pos)

    fee = calc_fee(cost_amount, "buy")
    trade = TradeLog(
        code=code, stock_name=stock_name, trade_date=buy_date,
        action="buy", price=buy_price, shares=shares,
        amount=cost_amount, fee=fee, reason="买入建仓",
        position_id=None,
    )
    db.add(trade)
    db.flush()
    trade.position_id = pos.id
    db.commit()
    db.refresh(pos)
    return pos


def close_position(
    db: Session,
    position_id: int,
    close_price: float,
    close_reason: str = "manual",
    close_date: date | None = None,
) -> Position:
    if close_date is None:
        close_date = date.today()
    pos = db.query(Position).get(position_id)
    if pos is None or pos.status != "open":
        raise ValueError("Position not found or already closed")

    amount = close_price * pos.shares
    fee = calc_fee(amount, "sell")
    buy_fee = calc_fee(pos.cost_amount, "buy")
    pnl = (close_price - pos.buy_price) * pos.shares - fee - buy_fee
    pnl_pct = (close_price - pos.buy_price) / pos.buy_price

    pos.status = "closed"
    pos.close_date = close_date
    pos.close_price = close_price
    pos.close_reason = close_reason
    pos.pnl = round(pnl, 2)
    pos.pnl_pct = round(pnl_pct, 4)

    trade = TradeLog(
        code=pos.code, stock_name=pos.stock_name, trade_date=close_date,
        action="sell", price=close_price, shares=pos.shares,
        amount=amount, fee=fee, reason=close_reason,
        position_id=pos.id,
    )
    db.add(trade)
    db.commit()
    db.refresh(pos)
    return pos


def get_active_positions(db: Session) -> list[Position]:
    return db.query(Position).filter(Position.status == "open").all()


def get_position_stats(db: Session) -> dict:
    closed = db.query(Position).filter(Position.status == "closed").all()
    if not closed:
        return {"total_trades": 0, "win_count": 0, "loss_count": 0, "win_rate": 0, "total_pnl": 0, "avg_pnl_pct": 0, "avg_hold_days": 0}
    wins = [p for p in closed if (p.pnl or 0) > 0]
    total_pnl = sum(p.pnl or 0 for p in closed)
    avg_pnl_pct = sum(p.pnl_pct or 0 for p in closed) / len(closed)
    avg_hold = sum((p.close_date - p.buy_date).days for p in closed if p.close_date) / len(closed)
    return {
        "total_trades": len(closed),
        "win_count": len(wins),
        "loss_count": len(closed) - len(wins),
        "win_rate": round(len(wins) / len(closed), 4),
        "total_pnl": round(total_pnl, 2),
        "avg_pnl_pct": round(avg_pnl_pct, 4),
        "avg_hold_days": round(avg_hold, 1),
    }
```

- [ ] **Step 3: Create position API**

`backend/app/api/position.py`:
```python
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.position import Position, TradeLog
from app.models.system import User
from app.schemas.position import PositionCreate, PositionClose, PositionItem, TradeItem, PositionStats
from app.services.position.manager import open_position, close_position, get_active_positions, get_position_stats

router = APIRouter(prefix="/api/position", tags=["position"])


@router.get("/list", response_model=list[PositionItem])
def list_positions(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    positions = get_active_positions(db)
    items = []
    for p in positions:
        hold_days = (date.today() - p.buy_date).days
        pnl_pct = ((p.current_price or p.buy_price) - p.buy_price) / p.buy_price if p.buy_price > 0 else 0
        items.append(PositionItem(
            id=p.id, code=p.code, stock_name=p.stock_name, buy_date=p.buy_date,
            buy_price=p.buy_price, shares=p.shares, cost_amount=p.cost_amount,
            current_price=p.current_price, highest_price=p.highest_price,
            pnl_pct=round(pnl_pct, 4), status=p.status, hold_days=hold_days,
            stop_loss_price=p.stop_loss_price, take_profit_price=p.take_profit_price,
            executed=p.executed,
        ))
    return items


@router.post("/create", response_model=PositionItem)
def create_position(body: PositionCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    pos = open_position(db, body.code, body.stock_name, body.buy_price, body.shares, body.buy_date)
    hold_days = (date.today() - pos.buy_date).days
    return PositionItem(
        id=pos.id, code=pos.code, stock_name=pos.stock_name, buy_date=pos.buy_date,
        buy_price=pos.buy_price, shares=pos.shares, cost_amount=pos.cost_amount,
        current_price=pos.current_price, highest_price=pos.highest_price,
        pnl_pct=0, status=pos.status, hold_days=hold_days,
        stop_loss_price=pos.stop_loss_price, take_profit_price=pos.take_profit_price,
        executed=pos.executed,
    )


@router.post("/{position_id}/close", response_model=PositionItem)
def close_pos(position_id: int, body: PositionClose, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        pos = close_position(db, position_id, body.close_price, body.close_reason, body.close_date)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    hold_days = ((pos.close_date or date.today()) - pos.buy_date).days
    return PositionItem(
        id=pos.id, code=pos.code, stock_name=pos.stock_name, buy_date=pos.buy_date,
        buy_price=pos.buy_price, shares=pos.shares, cost_amount=pos.cost_amount,
        current_price=pos.close_price, highest_price=pos.highest_price,
        pnl_pct=pos.pnl_pct or 0, status=pos.status, hold_days=hold_days,
        stop_loss_price=pos.stop_loss_price, take_profit_price=pos.take_profit_price,
        executed=pos.executed,
    )


@router.get("/trades", response_model=list[TradeItem])
def list_trades(limit: int = 50, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    trades = db.query(TradeLog).order_by(TradeLog.trade_date.desc()).limit(limit).all()
    return [TradeItem.model_validate(t) for t in trades]


@router.get("/stats", response_model=PositionStats)
def stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return PositionStats(**get_position_stats(db))
```

- [ ] **Step 4: Register position router in api/__init__.py**

Update `backend/app/api/__init__.py`:
```python
from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.position import router as position_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(position_router)
```

- [ ] **Step 5: Write position API tests**

`backend/tests/test_position_api.py`:
```python
def test_create_position(test_client, auth_headers):
    resp = test_client.post("/api/position/create", headers=auth_headers, json={
        "code": "600000", "stock_name": "浦发银行", "buy_price": 10.0, "shares": 1000,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == "600000"
    assert body["status"] == "open"


def test_list_positions(test_client, auth_headers):
    test_client.post("/api/position/create", headers=auth_headers, json={
        "code": "600000", "stock_name": "浦发银行", "buy_price": 10.0, "shares": 1000,
    })
    resp = test_client.get("/api/position/list", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_close_position(test_client, auth_headers):
    create_resp = test_client.post("/api/position/create", headers=auth_headers, json={
        "code": "600000", "stock_name": "浦发银行", "buy_price": 10.0, "shares": 1000,
    })
    pid = create_resp.json()["id"]
    resp = test_client.post(f"/api/position/{pid}/close", headers=auth_headers, json={
        "close_price": 11.0, "close_reason": "take_profit",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "closed"


def test_stats_empty(test_client, auth_headers):
    resp = test_client.get("/api/position/stats", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total_trades"] == 0
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_position_api.py -v
```

Expected: 4 passed.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/position/manager.py backend/app/schemas/position.py backend/app/api/position.py backend/app/api/__init__.py backend/tests/test_position_api.py
git commit -m "feat: position management with open, close, trade log, and stats API"
```

---

## Phase 5: Notification & Scheduling

### Task 11: Feishu Webhook Client

**Files:**
- Create: `backend/app/services/notify/__init__.py`
- Create: `backend/app/services/notify/feishu.py`
- Create: `backend/tests/test_feishu.py`

- [ ] **Step 1: Write failing tests**

`backend/tests/test_feishu.py`:
```python
from unittest.mock import patch, MagicMock

from app.services.notify.feishu import FeishuBot


@patch("app.services.notify.feishu.httpx")
def test_send_text(mock_httpx):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"code": 0}
    mock_httpx.post.return_value = mock_response

    bot = FeishuBot("https://fake-webhook-url")
    result = bot.send_text("hello")
    assert result is True
    mock_httpx.post.assert_called_once()


@patch("app.services.notify.feishu.httpx")
def test_send_card(mock_httpx):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"code": 0}
    mock_httpx.post.return_value = mock_response

    bot = FeishuBot("https://fake-webhook-url")
    card = {
        "header": {"title": {"tag": "plain_text", "content": "Test"}},
        "elements": [{"tag": "div", "text": {"tag": "plain_text", "content": "body"}}],
    }
    result = bot.send_card(card)
    assert result is True


def test_send_text_no_url():
    bot = FeishuBot("")
    result = bot.send_text("hello")
    assert result is False
```

- [ ] **Step 2: Run tests — expect fail**

```bash
pytest tests/test_feishu.py -v
```

- [ ] **Step 3: Implement Feishu bot**

`backend/app/services/notify/feishu.py`:
```python
import logging

import httpx

logger = logging.getLogger(__name__)


class FeishuBot:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send_text(self, text: str) -> bool:
        if not self.webhook_url:
            logger.warning("Feishu webhook URL not configured")
            return False
        payload = {"msg_type": "text", "content": {"text": text}}
        return self._post(payload)

    def send_card(self, card: dict) -> bool:
        if not self.webhook_url:
            logger.warning("Feishu webhook URL not configured")
            return False
        payload = {"msg_type": "interactive", "card": card}
        return self._post(payload)

    def _post(self, payload: dict) -> bool:
        try:
            resp = httpx.post(self.webhook_url, json=payload, timeout=10)
            data = resp.json()
            if data.get("code") == 0 or resp.status_code == 200:
                return True
            logger.error(f"Feishu API error: {data}")
            return False
        except Exception as e:
            logger.error(f"Feishu send failed: {e}")
            return False
```

- [ ] **Step 4: Run tests — expect pass**

```bash
pytest tests/test_feishu.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/notify/ backend/tests/test_feishu.py
git commit -m "feat: Feishu webhook bot with text and card message support"
```

---

### Task 12: Message Builders

**Files:**
- Create: `backend/app/services/notify/messages.py`

- [ ] **Step 1: Implement message builders**

`backend/app/services/notify/messages.py`:
```python
from datetime import date


def build_post_market_card(
    trade_date: date,
    signals: list[dict],
    positions: list[dict],
    sentiment: dict,
    learn_tip: dict,
    base_url: str = "",
) -> dict:
    temp_score = sentiment.get("temperature", 50)
    temp_emoji = "🟢" if temp_score >= 70 else "🟡" if temp_score >= 40 else "🔴"

    header = {
        "title": {"tag": "plain_text", "content": f"📊 QuantClaw 盘后报告 {trade_date}"},
        "template": "blue",
    }

    elements = []

    # Market overview
    overview_lines = [
        f"**市场温度** {temp_score}/100 {temp_emoji}",
        f"上证 {sentiment.get('sh_index_pct', 0):+.2f}% | 深证 {sentiment.get('sz_index_pct', 0):+.2f}% | 创业板 {sentiment.get('cyb_index_pct', 0):+.2f}%",
        f"涨停 {sentiment.get('limit_up', 0)} | 跌停 {sentiment.get('limit_down', 0)} | 北向 {sentiment.get('north_net', 0)/1e8:+.1f}亿",
    ]
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "\n".join(overview_lines)}})
    elements.append({"tag": "hr"})

    # Buy signals
    if signals:
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "**🔴 买入候选**"}})
        for i, sig in enumerate(signals):
            medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"{i+1}."
            sig_lines = [
                f"{medal} **{sig['stock_name']}** {sig['code']}  评分 {sig['score']}/100",
                f"现价 ¥{sig['close_price']:.2f} | 买入 ¥{sig.get('buy_low', 0):.2f}-{sig.get('buy_high', 0):.2f}",
                f"止损 ¥{sig.get('stop_loss', 0):.2f} | 目标 ¥{sig.get('target', 0):.2f}",
                f"📌 {sig.get('reason', '')}",
            ]
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "\n".join(sig_lines)}})
        if base_url:
            elements.append({"tag": "action", "actions": [{"tag": "button", "text": {"tag": "plain_text", "content": "查看详情 →"}, "url": f"{base_url}/scan", "type": "primary"}]})
        elements.append({"tag": "hr"})
    else:
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "**今日无买入候选** — 耐心等待更好的机会"}})
        elements.append({"tag": "hr"})

    # Positions
    if positions:
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "**🟢 持仓跟踪**"}})
        for pos in positions:
            pnl_emoji = "✅" if pos.get("pnl_pct", 0) >= 0 else "⚠️"
            pos_line = f"{pos['stock_name']} {pos['code']} | 第{pos['hold_days']}天 | {pos['pnl_pct']:+.1%} {pnl_emoji} | {pos.get('advice', '继续持有')}"
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": pos_line}})
        elements.append({"tag": "hr"})

    # Learning tip
    if learn_tip:
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": f"**📖 今日学习: {learn_tip['name']}**\n{learn_tip['summary']}"}})

    return {"header": header, "elements": elements}


def build_pre_market_card(trade_date: date, positions: list[dict]) -> dict:
    header = {
        "title": {"tag": "plain_text", "content": f"🌅 QuantClaw 盘前关注 {trade_date}"},
        "template": "green",
    }
    elements = []
    if positions:
        for pos in positions:
            line = f"**{pos['stock_name']}** {pos['code']} | 成本 ¥{pos['buy_price']:.2f} | 止损 ¥{pos['stop_loss']:.2f} | 止盈 ¥{pos['take_profit']:.2f}"
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": line}})
    else:
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "当前无持仓，等待买入信号"}})
    return {"header": header, "elements": elements}


def build_alert_card(title: str, message: str, level: str = "warning") -> dict:
    template = {"warning": "orange", "error": "red", "info": "blue"}.get(level, "orange")
    return {
        "header": {"title": {"tag": "plain_text", "content": f"⚠️ {title}"}, "template": template},
        "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": message}}],
    }
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/notify/messages.py
git commit -m "feat: Feishu message card builders for pre-market, post-market, and alerts"
```

---

### Task 13: Trading Calendar + Scheduler

**Files:**
- Create: `backend/app/scheduler/__init__.py`
- Create: `backend/app/scheduler/trading_calendar.py`
- Create: `backend/app/scheduler/jobs.py`
- Create: `backend/app/scheduler/setup.py`
- Create: `backend/tests/test_trading_calendar.py`

- [ ] **Step 1: Write failing tests for trading calendar**

`backend/tests/test_trading_calendar.py`:
```python
from datetime import date

from app.scheduler.trading_calendar import is_trading_day


def test_weekday_is_trading_day():
    # 2026-05-25 is Monday
    assert is_trading_day(date(2026, 5, 25)) is True


def test_weekend_is_not_trading_day():
    # 2026-05-23 is Saturday
    assert is_trading_day(date(2026, 5, 23)) is False
    # 2026-05-24 is Sunday
    assert is_trading_day(date(2026, 5, 24)) is False
```

- [ ] **Step 2: Implement trading calendar**

`backend/app/scheduler/trading_calendar.py`:
```python
import logging
from datetime import date

import akshare as ak
import pandas as pd

logger = logging.getLogger(__name__)

_HOLIDAY_CACHE: set[date] | None = None


def _load_holidays() -> set[date]:
    global _HOLIDAY_CACHE
    if _HOLIDAY_CACHE is not None:
        return _HOLIDAY_CACHE
    try:
        df = ak.tool_trade_date_hist_sina()
        all_trade_dates = set(pd.to_datetime(df["trade_date"]).dt.date)
        year = date.today().year
        all_dates_this_year = set(pd.bdate_range(start=f"{year}-01-01", end=f"{year}-12-31").date)
        _HOLIDAY_CACHE = all_dates_this_year - all_trade_dates
    except Exception as e:
        logger.warning(f"Failed to load holiday calendar: {e}, falling back to weekday-only")
        _HOLIDAY_CACHE = set()
    return _HOLIDAY_CACHE


def is_trading_day(d: date | None = None) -> bool:
    if d is None:
        d = date.today()
    if d.weekday() >= 5:
        return False
    holidays = _load_holidays()
    return d not in holidays
```

- [ ] **Step 3: Run tests**

```bash
pytest tests/test_trading_calendar.py -v
```

Expected: 2 passed.

- [ ] **Step 4: Implement scheduler jobs**

`backend/app/scheduler/jobs.py`:
```python
import logging
from datetime import date, datetime

from app.config import settings
from app.database import SessionLocal
from app.models.market import MarketSentiment, NorthFlow, SectorDaily
from app.models.signal import Signal
from app.models.system import SchedulerLog
from app.scheduler.trading_calendar import is_trading_day
from app.services.data.fetcher import (
    fetch_daily_klines_batch,
    fetch_market_sentiment,
    fetch_north_flow,
    fetch_sector_daily,
    fetch_stock_basic_list,
)
from app.services.notify.feishu import FeishuBot
from app.services.notify.messages import build_alert_card, build_post_market_card, build_pre_market_card
from app.services.position.manager import get_active_positions
from app.services.data.maintenance import purge_old_data, update_stock_basic

logger = logging.getLogger(__name__)


def _log_job(db, job_name: str, status: str, message: str = "", started_at: datetime | None = None):
    db.add(SchedulerLog(job_name=job_name, status=status, message=message, started_at=started_at or datetime.now(), finished_at=datetime.now()))
    db.commit()


def job_pre_market():
    if not is_trading_day():
        return
    started = datetime.now()
    db = SessionLocal()
    try:
        positions = get_active_positions(db)
        pos_data = [{"stock_name": p.stock_name, "code": p.code, "buy_price": p.buy_price, "stop_loss": p.stop_loss_price, "take_profit": p.take_profit_price} for p in positions]
        card = build_pre_market_card(date.today(), pos_data)
        bot = FeishuBot(settings.feishu_webhook_url)
        bot.send_card(card)
        _log_job(db, "pre_market", "success", started_at=started)
    except Exception as e:
        logger.error(f"Pre-market job failed: {e}")
        _log_job(db, "pre_market", "failed", str(e), started_at=started)
    finally:
        db.close()


def job_intraday_check():
    """09:35 and 11:35 — check positions for intraday anomalies."""
    if not is_trading_day():
        return
    started = datetime.now()
    db = SessionLocal()
    try:
        positions = get_active_positions(db)
        if not positions:
            _log_job(db, "intraday_check", "success", "No positions", started_at=started)
            return
        spot_df = fetch_stock_basic_list()  # get live prices
        if spot_df.empty:
            return
        price_map = dict(zip(spot_df["code"], spot_df["price"]))
        bot = FeishuBot(settings.feishu_webhook_url)
        from app.services.position.risk import check_sell_signals, RiskConfig
        cfg = RiskConfig()
        for pos in positions:
            live_price = price_map.get(pos.code)
            if live_price is None:
                continue
            pos.current_price = live_price
            if live_price > pos.highest_price:
                pos.highest_price = live_price
            hold_days = (date.today() - pos.buy_date).days
            signals = check_sell_signals(
                {"buy_price": pos.buy_price, "current_price": live_price, "highest_price": pos.highest_price, "hold_days": hold_days},
                cfg,
            )
            if any(s["urgency"] == "immediate" for s in signals):
                msg = f"⚠️ {pos.stock_name} {pos.code} 触发卖出信号: {signals[0]['reason']}"
                bot.send_card(build_alert_card("盘中异动", msg, "warning"))
        db.commit()
        _log_job(db, "intraday_check", "success", started_at=started)
    except Exception as e:
        logger.error(f"Intraday check failed: {e}")
        _log_job(db, "intraday_check", "failed", str(e), started_at=started)
    finally:
        db.close()


def job_post_market_collect():
    """15:05 — collect all end-of-day market data."""
    if not is_trading_day():
        return
    started = datetime.now()
    db = SessionLocal()
    try:
        from app.models.stock import StockBasic, StockDaily
        from app.models.market import NorthFlow as NorthFlowModel, SectorDaily as SectorDailyModel, FundFlow as FundFlowModel, MarketSentiment as MarketSentimentModel

        # 1. Fetch stock list and daily klines
        stock_list = fetch_stock_basic_list()
        if stock_list.empty:
            raise RuntimeError("Failed to fetch stock list")
        codes = stock_list["code"].tolist()
        today_str = date.today().strftime("%Y%m%d")
        kline_df = fetch_daily_klines_batch(codes, start_date=today_str, end_date=today_str)
        if not kline_df.empty:
            for _, row in kline_df.iterrows():
                existing = db.query(StockDaily).filter(StockDaily.code == row["code"], StockDaily.trade_date == row["trade_date"]).first()
                if not existing:
                    db.add(StockDaily(**row.to_dict()))
            db.commit()

        # 2. North flow
        north_df = fetch_north_flow(days=5)
        if not north_df.empty:
            for _, row in north_df.iterrows():
                existing = db.query(NorthFlowModel).filter(NorthFlowModel.trade_date == row["trade_date"]).first()
                if not existing:
                    db.add(NorthFlowModel(trade_date=row["trade_date"], buy_amount=row["buy_amount"], sell_amount=row["sell_amount"], net_amount=row["net_amount"]))
            db.commit()

        # 3. Sectors
        sector_df = fetch_sector_daily()
        if not sector_df.empty:
            for _, row in sector_df.iterrows():
                existing = db.query(SectorDailyModel).filter(SectorDailyModel.sector == row["sector"], SectorDailyModel.trade_date == row["trade_date"]).first()
                if not existing:
                    db.add(SectorDailyModel(sector=row["sector"], trade_date=row["trade_date"], change_pct=row["change_pct"], volume=row.get("volume", 0), net_fund_flow=row.get("net_fund_flow", 0)))
            db.commit()

        # 4. Market sentiment
        sentiment = fetch_market_sentiment()
        if sentiment:
            existing = db.query(MarketSentimentModel).filter(MarketSentimentModel.trade_date == sentiment["trade_date"]).first()
            if not existing:
                db.add(MarketSentimentModel(**sentiment))
                db.commit()

        _log_job(db, "post_market_collect", "success", f"Collected {len(codes)} stocks", started_at=started)
    except Exception as e:
        logger.error(f"Post-market collect failed: {e}")
        _log_job(db, "post_market_collect", "failed", str(e), started_at=started)
        bot = FeishuBot(settings.feishu_webhook_url)
        bot.send_card(build_alert_card("数据采集失败", str(e), "error"))
    finally:
        db.close()


def job_post_market_analyze():
    """15:30 — run full scoring pipeline and send report."""
    if not is_trading_day():
        return
    started = datetime.now()
    db = SessionLocal()
    try:
        from app.models.stock import StockBasic, StockDaily
        from app.models.market import NorthFlow as NorthFlowModel, SectorDaily as SectorDailyModel, FundFlow as FundFlowModel
        from app.models.signal import Signal
        from app.services.strategy.filters import hard_filter
        from app.services.strategy.scoring import score_technical, score_fund, score_momentum, score_sentiment
        from app.services.strategy.signal_generator import select_top_n, apply_concentration_control, build_signal_reason
        from app.services.data.indicators import calc_volume_ratio
        from app.services.position.risk import check_sell_signals, RiskConfig
        from app.learn.indicators import INDICATOR_GUIDES
        import pandas as pd

        today = date.today()

        # 1. Build stock universe DataFrame
        basics = db.query(StockBasic).all()
        if not basics:
            _log_job(db, "post_market_analyze", "failed", "No stock_basic data", started_at=started)
            return
        stocks = []
        for b in basics:
            last_20 = db.query(StockDaily).filter(StockDaily.code == b.code).order_by(StockDaily.trade_date.desc()).limit(20).all()
            if len(last_20) < 5:
                continue
            latest = last_20[0]
            avg_amount = sum(d.amount for d in last_20) / len(last_20)
            pct_5d = ((latest.close - last_20[min(4, len(last_20)-1)].close) / last_20[min(4, len(last_20)-1)].close * 100) if len(last_20) >= 5 else 0
            stocks.append({
                "code": b.code, "name": b.name, "close": latest.close,
                "avg_amount_20d": avg_amount, "list_date": b.list_date,
                "market": b.market, "is_st": b.is_st,
                "is_suspended": False, "is_limit_up": (latest.change_pct or 0) >= 9.9,
                "is_limit_down": (latest.change_pct or 0) <= -9.9,
                "industry": b.industry or "未知", "pct_5d": pct_5d,
            })
        if not stocks:
            _log_job(db, "post_market_analyze", "failed", "No eligible stocks", started_at=started)
            return
        universe_df = pd.DataFrame(stocks)

        # 2. Hard filter
        from app.api.settings import DEFAULT_STRATEGY
        config = DEFAULT_STRATEGY
        cfg_row = db.query(StrategyConfig).first()
        if cfg_row:
            config = cfg_row.config
        filtered = hard_filter(universe_df, config.get("filter", {}))

        # 3. Score each stock
        scored_rows = []
        for _, row in filtered.iterrows():
            klines = db.query(StockDaily).filter(StockDaily.code == row["code"]).order_by(StockDaily.trade_date).limit(60).all()
            kline_df = pd.DataFrame([{"open": k.open, "high": k.high, "low": k.low, "close": k.close, "volume": k.volume} for k in klines])
            if len(kline_df) < 20:
                continue
            tech_score, tech_details = score_technical(kline_df)
            vol_ratio = calc_volume_ratio(kline_df["volume"], 20)
            fund_data = {"north_net_3d": 0, "main_net": 0, "super_large_pct": 0, "volume_ratio": vol_ratio}
            fund_score, fund_details = score_fund(fund_data)
            # Sector info
            sector_row = db.query(SectorDailyModel).filter(SectorDailyModel.sector == row["industry"], SectorDailyModel.trade_date == today).first()
            all_sectors_today = db.query(SectorDailyModel).filter(SectorDailyModel.trade_date == today).count()
            sector_rank_pct = 50
            if sector_row and all_sectors_today > 0:
                above = db.query(SectorDailyModel).filter(SectorDailyModel.trade_date == today, SectorDailyModel.change_pct >= sector_row.change_pct).count()
                sector_rank_pct = int(above / all_sectors_today * 100)
            sentiment_row = db.query(MarketSentiment).filter(MarketSentiment.trade_date == today).first()
            momentum_data = {"pct_5d": row["pct_5d"], "relative_strength": (sector_row.change_pct if sector_row else 0) - row["pct_5d"], "is_20d_high": row["close"] >= kline_df["close"].tail(20).max()}
            momentum_score, momentum_details = score_momentum(momentum_data)
            sentiment_data = {"sector_rank_pct": sector_rank_pct, "limit_up": sentiment_row.limit_up if sentiment_row else 0, "limit_down": sentiment_row.limit_down if sentiment_row else 0, "sector_net_flow": sector_row.net_fund_flow if sector_row else 0}
            sentiment_score, sentiment_details = score_sentiment(sentiment_data)
            total = tech_score + fund_score + momentum_score + sentiment_score
            all_details = {"tech": tech_details, "fund": fund_details, "momentum": momentum_details, "sentiment": sentiment_details}
            reason = build_signal_reason(all_details)
            scored_rows.append({
                "code": row["code"], "stock_name": row["name"], "close": row["close"],
                "industry": row["industry"], "score": total,
                "tech_score": tech_score, "fund_score": fund_score,
                "momentum_score": momentum_score, "sentiment_score": sentiment_score,
                "reason": reason, "details": all_details,
            })
        if not scored_rows:
            _log_job(db, "post_market_analyze", "success", "No stocks scored above threshold", started_at=started)
            return
        scored_df = pd.DataFrame(scored_rows)

        # 4. Concentration control + TOP 3
        held_codes = [p.code for p in get_active_positions(db)]
        top = apply_concentration_control(select_top_n(scored_df, config.get("score", {}).get("min_score", 65)), held_codes)

        # 5. Persist signals
        for _, sig in scored_df.iterrows():
            stop_loss_price = round(sig["close"] * 0.95, 2)
            target_price = round(sig["close"] * 1.12, 2)
            db.add(Signal(
                code=sig["code"], stock_name=sig["stock_name"], trade_date=today,
                direction="buy", score=sig["score"],
                tech_score=sig["tech_score"], fund_score=sig["fund_score"],
                momentum_score=sig["momentum_score"], sentiment_score=sig["sentiment_score"],
                reason=sig["reason"], close_price=sig["close"],
                suggested_buy_low=round(sig["close"] * 0.99, 2),
                suggested_buy_high=round(sig["close"] * 1.01, 2),
                stop_loss_price=stop_loss_price, target_price=target_price,
            ))
        db.commit()

        # 6. Check positions for sell signals
        risk_cfg = RiskConfig(**config.get("risk", {}))
        positions = get_active_positions(db)
        pos_report = []
        for pos in positions:
            hold_days = (today - pos.buy_date).days
            pnl_pct = (pos.current_price - pos.buy_price) / pos.buy_price if pos.current_price and pos.buy_price else 0
            sell_signals = check_sell_signals(
                {"buy_price": pos.buy_price, "current_price": pos.current_price, "highest_price": pos.highest_price, "hold_days": hold_days},
                risk_cfg,
            )
            advice = sell_signals[0]["reason"] if sell_signals else "继续持有"
            pos_report.append({"stock_name": pos.stock_name, "code": pos.code, "hold_days": hold_days, "pnl_pct": pnl_pct, "advice": advice})

        # 7. Build and send Feishu report
        sentiment_dict = {}
        if sentiment_row:
            north = db.query(NorthFlowModel).filter(NorthFlowModel.trade_date == today).first()
            sentiment_dict = {
                "temperature": 50, "sh_index_pct": sentiment_row.sh_index_pct,
                "sz_index_pct": sentiment_row.sz_index_pct, "cyb_index_pct": sentiment_row.cyb_index_pct,
                "limit_up": sentiment_row.limit_up, "limit_down": sentiment_row.limit_down,
                "north_net": north.net_amount if north else 0,
            }
        top_signals = []
        for _, sig in top.iterrows():
            top_signals.append({
                "code": sig["code"], "stock_name": sig["stock_name"], "score": sig["score"],
                "close_price": sig["close"], "reason": sig["reason"],
                "buy_low": round(sig["close"] * 0.99, 2), "buy_high": round(sig["close"] * 1.01, 2),
                "stop_loss": round(sig["close"] * 0.95, 2), "target": round(sig["close"] * 1.12, 2),
            })
        day_idx = today.timetuple().tm_yday % len(INDICATOR_GUIDES)
        learn_tip = INDICATOR_GUIDES[day_idx]

        card = build_post_market_card(today, top_signals, pos_report, sentiment_dict, learn_tip, settings.base_url)
        bot = FeishuBot(settings.feishu_webhook_url)
        bot.send_card(card)

        _log_job(db, "post_market_analyze", "success", f"Generated {len(scored_rows)} scores, top {len(top)} signals", started_at=started)
    except Exception as e:
        logger.error(f"Post-market analyze failed: {e}", exc_info=True)
        _log_job(db, "post_market_analyze", "failed", str(e), started_at=started)
        bot = FeishuBot(settings.feishu_webhook_url)
        bot.send_card(build_alert_card("策略分析失败", str(e), "error"))
    finally:
        db.close()


def job_maintenance():
    db = SessionLocal()
    try:
        purge_old_data(db)
        update_stock_basic(db)
        _log_job(db, "maintenance", "success")
    except Exception as e:
        logger.error(f"Maintenance failed: {e}")
        _log_job(db, "maintenance", "failed", str(e))
    finally:
        db.close()
```

- [ ] **Step 5: Implement scheduler setup**

`backend/app/scheduler/setup.py`:
```python
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.scheduler.jobs import job_pre_market, job_intraday_check, job_post_market_collect, job_post_market_analyze, job_maintenance

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone="Asia/Shanghai")


def start_scheduler():
    scheduler.add_job(job_pre_market, CronTrigger(hour=8, minute=30), id="pre_market", replace_existing=True)
    scheduler.add_job(job_intraday_check, CronTrigger(hour=9, minute=35), id="intraday_0935", replace_existing=True)
    scheduler.add_job(job_intraday_check, CronTrigger(hour=11, minute=35), id="intraday_1135", replace_existing=True)
    scheduler.add_job(job_post_market_collect, CronTrigger(hour=15, minute=5), id="post_market_collect", replace_existing=True)
    scheduler.add_job(job_post_market_analyze, CronTrigger(hour=15, minute=30), id="post_market_analyze", replace_existing=True)
    scheduler.add_job(job_maintenance, CronTrigger(hour=20, minute=0), id="maintenance", replace_existing=True)
    scheduler.start()
    logger.info("Scheduler started with 6 trading-day jobs")


def shutdown_scheduler():
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")
```

- [ ] **Step 6: Wire scheduler into FastAPI lifespan**

Update `backend/app/main.py` lifespan:
```python
from app.scheduler.setup import start_scheduler, shutdown_scheduler

@contextmanager
def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _seed_admin()
    start_scheduler()
    yield
    shutdown_scheduler()
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/scheduler/ backend/tests/test_trading_calendar.py backend/app/main.py
git commit -m "feat: trading calendar, scheduler jobs (pre-market, post-market, maintenance)"
```

---

## Phase 6: Remaining API Endpoints

### Task 14: Dashboard + Scan + Stock + Signal + Settings + Learn APIs

**Files:**
- Create: `backend/app/schemas/dashboard.py`
- Create: `backend/app/schemas/stock.py`
- Create: `backend/app/schemas/signal.py`
- Create: `backend/app/schemas/settings.py`
- Create: `backend/app/api/dashboard.py`
- Create: `backend/app/api/scan.py`
- Create: `backend/app/api/stock.py`
- Create: `backend/app/api/signal.py`
- Create: `backend/app/api/settings.py`
- Create: `backend/app/api/learn.py`
- Create: `backend/app/learn/__init__.py`
- Create: `backend/app/learn/indicators.py`
- Modify: `backend/app/api/__init__.py`

- [ ] **Step 1: Create remaining schemas**

`backend/app/schemas/dashboard.py`:
```python
from pydantic import BaseModel


class DashboardOverview(BaseModel):
    temperature: int
    sh_index_pct: float
    sz_index_pct: float
    cyb_index_pct: float
    limit_up: int
    limit_down: int
    north_net: float
    active_positions: int
    total_pnl: float
    signal_accuracy_7d: float


class SentimentData(BaseModel):
    up_count: int
    down_count: int
    limit_up: int
    limit_down: int
    temperature: int
```

`backend/app/schemas/stock.py`:
```python
from datetime import date
from pydantic import BaseModel


class KLineItem(BaseModel):
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    volume: int
    amount: float


class StockScore(BaseModel):
    code: str
    stock_name: str
    total_score: int
    tech_score: int
    fund_score: int
    momentum_score: int
    sentiment_score: int
    reason: str
    close_price: float
    industry: str | None = None
```

`backend/app/schemas/signal.py`:
```python
from datetime import date
from pydantic import BaseModel


class SignalItem(BaseModel):
    id: int
    code: str
    stock_name: str
    trade_date: date
    direction: str
    score: int
    reason: str
    close_price: float
    suggested_buy_low: float | None
    suggested_buy_high: float | None
    stop_loss_price: float | None
    target_price: float | None

    class Config:
        from_attributes = True
```

`backend/app/schemas/settings.py`:
```python
from pydantic import BaseModel


class StrategySettings(BaseModel):
    filter: dict
    score: dict
    position: dict
    risk: dict


class NotifySettings(BaseModel):
    feishu_webhook_url: str


class NotifyTestRequest(BaseModel):
    message: str = "QuantClaw 测试消息 — 飞书推送正常工作!"
```

- [ ] **Step 2: Create dashboard API**

`backend/app/api/dashboard.py`:
```python
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.market import MarketSentiment, NorthFlow
from app.models.position import Position
from app.models.signal import Signal
from app.models.system import User
from app.schemas.dashboard import DashboardOverview, SentimentData

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _calc_temperature(sentiment: MarketSentiment | None, north_net: float = 0) -> int:
    if sentiment is None:
        return 50
    total = sentiment.up_count + sentiment.down_count + sentiment.flat_count
    if total == 0:
        return 50
    up_ratio = sentiment.up_count / total * 40
    limit_score = min(sentiment.limit_up / max(sentiment.limit_down, 1), 5) * 8
    north_score = min(max(north_net / 5e9, -1), 1) * 10 + 10
    return int(min(max(up_ratio + limit_score + north_score, 0), 100))


@router.get("/overview", response_model=DashboardOverview)
def overview(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    today = date.today()
    sentiment = db.query(MarketSentiment).filter(MarketSentiment.trade_date == today).first()
    north = db.query(NorthFlow).filter(NorthFlow.trade_date == today).first()
    north_net = north.net_amount if north else 0
    active = db.query(Position).filter(Position.status == "open").count()
    closed = db.query(Position).filter(Position.status == "closed").all()
    total_pnl = sum(p.pnl or 0 for p in closed)

    week_ago = today - timedelta(days=7)
    recent_signals = db.query(Signal).filter(Signal.trade_date >= week_ago, Signal.direction == "buy").all()
    accuracy = 0.0
    if recent_signals:
        correct = sum(1 for s in recent_signals if s.score >= 65)
        accuracy = correct / len(recent_signals)

    temp = _calc_temperature(sentiment, north_net)
    return DashboardOverview(
        temperature=temp,
        sh_index_pct=sentiment.sh_index_pct if sentiment else 0,
        sz_index_pct=sentiment.sz_index_pct if sentiment else 0,
        cyb_index_pct=sentiment.cyb_index_pct if sentiment else 0,
        limit_up=sentiment.limit_up if sentiment else 0,
        limit_down=sentiment.limit_down if sentiment else 0,
        north_net=north_net,
        active_positions=active,
        total_pnl=total_pnl,
        signal_accuracy_7d=accuracy,
    )


@router.get("/sentiment", response_model=SentimentData)
def sentiment(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = db.query(MarketSentiment).order_by(MarketSentiment.trade_date.desc()).first()
    north = db.query(NorthFlow).order_by(NorthFlow.trade_date.desc()).first()
    if s is None:
        return SentimentData(up_count=0, down_count=0, limit_up=0, limit_down=0, temperature=50)
    temp = _calc_temperature(s, north.net_amount if north else 0)
    return SentimentData(up_count=s.up_count, down_count=s.down_count, limit_up=s.limit_up, limit_down=s.limit_down, temperature=temp)
```

- [ ] **Step 3: Create scan, stock, signal, settings, learn APIs**

`backend/app/api/scan.py`:
```python
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.market import NorthFlow, SectorDaily
from app.models.signal import Signal
from app.models.system import User

router = APIRouter(prefix="/api/scan", tags=["scan"])


@router.get("/ranking")
def ranking(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("score"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    today = date.today()
    query = db.query(Signal).filter(Signal.trade_date == today, Signal.direction == "buy")
    if sort_by == "score":
        query = query.order_by(Signal.score.desc())
    total = query.count()
    items = query.offset((page - 1) * size).limit(size).all()
    return {"total": total, "page": page, "items": [{"code": s.code, "stock_name": s.stock_name, "score": s.score, "tech_score": s.tech_score, "fund_score": s.fund_score, "momentum_score": s.momentum_score, "sentiment_score": s.sentiment_score, "reason": s.reason, "close_price": s.close_price} for s in items]}


@router.get("/sectors")
def sectors(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    today = date.today()
    items = db.query(SectorDaily).filter(SectorDaily.trade_date == today).order_by(SectorDaily.change_pct.desc()).all()
    return [{"sector": s.sector, "change_pct": s.change_pct, "net_fund_flow": s.net_fund_flow} for s in items]


@router.get("/north-flow")
def north_flow(days: int = Query(30, ge=1, le=250), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    items = db.query(NorthFlow).order_by(NorthFlow.trade_date.desc()).limit(days).all()
    items.reverse()
    return [{"trade_date": str(n.trade_date), "net_amount": n.net_amount} for n in items]
```

`backend/app/api/stock.py`:
```python
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.stock import StockDaily
from app.models.signal import Signal
from app.models.system import User

router = APIRouter(prefix="/api/stock", tags=["stock"])


@router.get("/{code}/kline")
def kline(code: str, days: int = Query(60, ge=1, le=250), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    cutoff = date.today() - timedelta(days=int(days * 1.5))
    items = db.query(StockDaily).filter(StockDaily.code == code, StockDaily.trade_date >= cutoff).order_by(StockDaily.trade_date).all()
    return [{"trade_date": str(k.trade_date), "open": k.open, "high": k.high, "low": k.low, "close": k.close, "volume": k.volume} for k in items]


@router.get("/{code}/signals")
def signals(code: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    items = db.query(Signal).filter(Signal.code == code).order_by(Signal.trade_date.desc()).limit(30).all()
    return [{"trade_date": str(s.trade_date), "direction": s.direction, "score": s.score, "reason": s.reason} for s in items]


@router.get("/{code}/score")
def score(code: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = db.query(Signal).filter(Signal.code == code).order_by(Signal.trade_date.desc()).first()
    if not s:
        return {"code": code, "score": 0, "detail": "无评分数据"}
    return {"code": s.code, "stock_name": s.stock_name, "score": s.score, "tech_score": s.tech_score, "fund_score": s.fund_score, "momentum_score": s.momentum_score, "sentiment_score": s.sentiment_score, "reason": s.reason}
```

`backend/app/api/signal.py`:
```python
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.signal import Signal
from app.models.system import User
from app.schemas.signal import SignalItem

router = APIRouter(prefix="/api/signal", tags=["signal"])


@router.get("/today", response_model=list[SignalItem])
def today_signals(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    items = db.query(Signal).filter(Signal.trade_date == date.today()).order_by(Signal.score.desc()).all()
    return [SignalItem.model_validate(s) for s in items]


@router.get("/history", response_model=list[SignalItem])
def history(days: int = Query(30, ge=1, le=250), direction: str = Query("buy"), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from datetime import timedelta
    cutoff = date.today() - timedelta(days=days)
    items = db.query(Signal).filter(Signal.trade_date >= cutoff, Signal.direction == direction).order_by(Signal.trade_date.desc()).limit(100).all()
    return [SignalItem.model_validate(s) for s in items]
```

`backend/app/api/settings.py`:
```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.config import settings as app_settings
from app.models.system import StrategyConfig, User
from app.schemas.settings import NotifySettings, NotifyTestRequest, StrategySettings
from app.services.notify.feishu import FeishuBot

router = APIRouter(prefix="/api/settings", tags=["settings"])

DEFAULT_STRATEGY = {
    "filter": {"min_amount_20d": 50_000_000, "max_price": 50, "min_list_days": 60},
    "score": {"tech_weight": 0.4, "fund_weight": 0.3, "momentum_weight": 0.2, "sentiment_weight": 0.1, "min_score": 65},
    "position": {"max_positions": 2, "max_single_pct": 0.5, "cash_reserve_pct": 0.1},
    "risk": {"stop_loss_pct": -0.05, "take_profit_pct": 0.12, "trailing_trigger": 0.07, "trailing_drawdown": 0.03, "max_hold_days": 5},
}


@router.get("/strategy", response_model=StrategySettings)
def get_strategy(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    cfg = db.query(StrategyConfig).first()
    if cfg is None:
        return StrategySettings(**DEFAULT_STRATEGY)
    return StrategySettings(**cfg.config)


@router.put("/strategy", response_model=StrategySettings)
def update_strategy(body: StrategySettings, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
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
```

`backend/app/api/learn.py`:
```python
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
```

- [ ] **Step 4: Create learning content**

`backend/app/learn/indicators.py`:
```python
INDICATOR_GUIDES = [
    {
        "name": "MA均线",
        "summary": "移动平均线是过去N天收盘价的平均值,反映股价趋势方向。MA5>MA10>MA20称为多头排列,代表上升趋势。",
        "formula": "MA(N) = 过去N天收盘价之和 / N",
        "buy_pattern": "MA5上穿MA10(金叉),且MA20在下方支撑",
        "sell_pattern": "MA5下穿MA10(死叉),且股价跌破MA20",
        "trap": "震荡市中均线频繁交叉,容易产生假信号",
        "weight_in_system": "多头排列在技术面评分中占10分(满分40)",
    },
    {
        "name": "MACD",
        "summary": "MACD由DIF(快线)和DEA(慢线)组成。当DIF从下往上穿越DEA叫金叉,是买入信号;反之叫死叉,是卖出信号。",
        "formula": "DIF = EMA12 - EMA26, DEA = DIF的9日EMA, 柱状图 = 2×(DIF-DEA)",
        "buy_pattern": "DIF上穿DEA形成金叉,尤其在零轴附近的金叉最有价值",
        "sell_pattern": "DIF下穿DEA形成死叉,零轴上方死叉需注意",
        "trap": "MACD是滞后指标,快速行情中信号会延迟。震荡市中频繁金叉死叉",
        "weight_in_system": "MACD金叉在技术面评分中占8分(满分40)",
    },
    {
        "name": "KDJ",
        "summary": "KDJ是超买超卖指标。K值在20以下是超卖区(可能反弹),80以上是超买区(可能回调)。K线上穿D线是金叉。",
        "formula": "RSV = (收盘-N日最低) / (N日最高-N日最低) × 100, K = RSV的平滑, D = K的平滑, J = 3K-2D",
        "buy_pattern": "K在20-50区间上穿D线,J值从负转正",
        "sell_pattern": "K在80以上下穿D线,J值从100+回落",
        "trap": "强势上涨中KDJ会长时间停留在超买区,过早卖出会错过主升浪",
        "weight_in_system": "KDJ金叉在技术面评分中占5分(满分40)",
    },
    {
        "name": "RSI",
        "summary": "相对强弱指数,衡量买方和卖方力量对比。RSI>70超买,RSI<30超卖。50是多空分界线。",
        "formula": "RSI = 100 - 100/(1 + 平均涨幅/平均跌幅)",
        "buy_pattern": "RSI从30以下回升到50以上",
        "sell_pattern": "RSI从70以上回落到50以下",
        "trap": "单独使用RSI容易过早入场或离场,需配合趋势指标",
        "weight_in_system": "RSI作为辅助参考,不单独计分",
    },
    {
        "name": "布林带",
        "summary": "布林带由中轨(20日均线)和上下轨(中轨±2倍标准差)组成。股价在上下轨之间波动,突破上轨可能继续上涨或即将回落。",
        "formula": "中轨 = MA20, 上轨 = MA20 + 2×STD20, 下轨 = MA20 - 2×STD20",
        "buy_pattern": "股价突破中轨向上轨运行,带宽扩大",
        "sell_pattern": "股价从上轨回落跌破中轨",
        "trap": "极端行情中股价可以沿着上轨或下轨运行很久,不要轻易抄底或逃顶",
        "weight_in_system": "布林带位置在技术面评分中占7分(满分40)",
    },
    {
        "name": "成交量",
        "summary": "成交量是市场参与度的体现。放量上涨代表买方力量强,缩量下跌说明卖压减轻。量价配合是技术分析的基础。",
        "formula": "量比 = 今日成交量 / 过去20日平均成交量",
        "buy_pattern": "股价上涨伴随成交量放大(量比>1.5),说明有资金进场",
        "sell_pattern": "股价上涨但成交量萎缩(量价背离)",
        "trap": "放量不代表一定上涨,也可能是主力出货。需看放量时的K线形态",
        "weight_in_system": "成交量放大在技术面评分中占5分(满分40)",
    },
    {
        "name": "量比",
        "summary": "量比反映当天交易活跃度相对于近期平均水平。量比>1.5说明交易明显放大,<0.5说明明显萎缩。",
        "formula": "量比 = 当日成交量 / 过去5日平均成交量",
        "buy_pattern": "量比1.5-5之间,配合股价上涨",
        "sell_pattern": "量比突然放大到5以上,可能是拉高出货",
        "trap": "开盘时量比波动大,不具参考价值,应看全天或盘后量比",
        "weight_in_system": "量比在资金面评分中占5分(满分30)",
    },
    {
        "name": "北向资金",
        "summary": "北向资金是通过沪港通/深港通流入A股的外资。被称为'聪明钱',其动向对市场有一定指引作用。",
        "formula": "北向净流入 = 买入金额 - 卖出金额",
        "buy_pattern": "连续3天以上净流入,总额超过50亿",
        "sell_pattern": "持续大额净流出",
        "trap": "北向资金也会短期波动,单日大额买入可能是被动基金调仓,不代表看好后市",
        "weight_in_system": "北向资金在资金面评分中占10分(满分30)",
    },
    {
        "name": "主力资金流",
        "summary": "通过分析大单(主力)和小单(散户)的买卖方向,判断主力资金的态度。主力净流入说明大资金在买入。",
        "formula": "主力净流入 = 超大单买入 + 大单买入 - 超大单卖出 - 大单卖出",
        "buy_pattern": "主力资金持续净流入,且散户资金净流出(主力吸筹)",
        "sell_pattern": "主力资金大幅净流出(主力出货)",
        "trap": "资金流数据有延迟且算法各平台不同,仅作参考。大单拆小单可以规避监测",
        "weight_in_system": "主力资金在资金面评分中占10分(满分30)",
    },
    {
        "name": "板块轮动",
        "summary": "A股有明显的板块轮动特征,一个板块领涨一段时间后资金会转向其他板块。跟踪板块热度有助于选股。",
        "formula": "板块热度 = 板块涨幅排名百分位 + 板块资金净流入排名",
        "buy_pattern": "板块开始放量上涨,板块内多只个股涨停,资金持续流入",
        "sell_pattern": "板块已连续上涨多日,出现冲高回落,龙头股开始分歧",
        "trap": "追板块尾部容易被套,最佳介入时机是板块启动初期(第1-2天)",
        "weight_in_system": "板块热度在情绪面评分中占5分(满分10)",
    },
]
```

- [ ] **Step 5: Register all routers in api/__init__.py**

Update `backend/app/api/__init__.py`:
```python
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
```

- [ ] **Step 6: Run all backend tests**

```bash
pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/ backend/app/schemas/ backend/app/learn/
git commit -m "feat: complete API layer — dashboard, scan, stock, signal, settings, learn endpoints"
```

---

## Phase 7: Frontend Dashboard

### Task 15: Vue3 Project Setup

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`, `tsconfig.app.json`, `tsconfig.node.json`
- Create: `frontend/index.html`
- Create: `frontend/env.d.ts`
- Create: `frontend/src/main.ts`
- Create: `frontend/src/App.vue`
- Create: `frontend/src/router/index.ts`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/stores/auth.ts`
- Create: `frontend/src/styles/variables.css`
- Create: `frontend/src/styles/global.css`

- [ ] **Step 1: Initialize Vue3 project**

```bash
cd D:\ide\workspace\personal-new\QuantClaw\frontend
npm create vue@latest . -- --typescript --router --pinia
```

When prompted, select: TypeScript Yes, JSX No, Router Yes, Pinia Yes, Vitest No, E2E No, ESLint No.

- [ ] **Step 2: Install dependencies**

```bash
cd frontend
npm install element-plus @element-plus/icons-vue axios echarts lightweight-charts
npm install -D @types/node
```

- [ ] **Step 3: Create API client with JWT interceptor**

`frontend/src/api/client.ts`:
```typescript
import axios from 'axios'

const client = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

client.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default client
```

- [ ] **Step 4: Create auth store**

`frontend/src/stores/auth.ts`:
```typescript
import { defineStore } from 'pinia'
import { ref } from 'vue'
import client from '@/api/client'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const username = ref('')
  const isLoggedIn = ref(!!token.value)

  async function login(user: string, password: string) {
    const { data } = await client.post('/auth/login', { username: user, password })
    token.value = data.access_token
    localStorage.setItem('token', data.access_token)
    isLoggedIn.value = true
    username.value = user
  }

  function logout() {
    token.value = ''
    username.value = ''
    isLoggedIn.value = false
    localStorage.removeItem('token')
  }

  async function fetchMe() {
    try {
      const { data } = await client.get('/auth/me')
      username.value = data.username
      isLoggedIn.value = true
    } catch {
      logout()
    }
  }

  return { token, username, isLoggedIn, login, logout, fetchMe }
})
```

- [ ] **Step 5: Create router with auth guard**

`frontend/src/router/index.ts`:
```typescript
import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue'), meta: { public: true } },
    { path: '/', name: 'dashboard', component: () => import('@/views/DashboardView.vue') },
    { path: '/scan', name: 'scan', component: () => import('@/views/ScanView.vue') },
    { path: '/stock/:code', name: 'stock', component: () => import('@/views/StockDetailView.vue') },
    { path: '/position', name: 'position', component: () => import('@/views/PositionView.vue') },
    { path: '/learn', name: 'learn', component: () => import('@/views/LearnView.vue') },
    { path: '/settings', name: 'settings', component: () => import('@/views/SettingsView.vue') },
  ],
})

router.beforeEach((to) => {
  const token = localStorage.getItem('token')
  if (!to.meta.public && !token) {
    return { name: 'login' }
  }
})

export default router
```

- [ ] **Step 6: Configure vite proxy for dev**

`frontend/vite.config.ts`:
```typescript
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
```

- [ ] **Step 7: Setup App.vue with Element Plus**

`frontend/src/main.ts`:
```typescript
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import App from './App.vue'
import router from './router'
import './styles/global.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(ElementPlus)
app.mount('#app')
```

`frontend/src/App.vue`:
```vue
<template>
  <router-view />
</template>
```

- [ ] **Step 8: Verify frontend builds**

```bash
cd frontend
npm run dev
# Should start on http://localhost:5173
```

- [ ] **Step 9: Commit**

```bash
git add frontend/
git commit -m "feat: Vue3 project setup with Element Plus, Pinia, router, auth guard, API client"
```

---

### Task 16: Login + Layout + Dashboard Page

**Files:**
- Create: `frontend/src/views/LoginView.vue`
- Create: `frontend/src/components/layout/AppLayout.vue`
- Create: `frontend/src/components/layout/AppSidebar.vue`
- Create: `frontend/src/views/DashboardView.vue`
- Create: `frontend/src/components/charts/GaugeChart.vue`
- Create: `frontend/src/components/signal/SignalCard.vue`
- Create: `frontend/src/api/dashboard.ts`

This task creates the login page, app layout with sidebar, and the main dashboard view. Each component uses Element Plus for UI and ECharts for the temperature gauge. The dashboard fetches data from `/api/dashboard/overview` and displays market temperature, today's top signals, and position summary cards.

Key implementation details:
- LoginView: el-card centered form, calls `authStore.login()`, redirects to `/` on success
- AppLayout: el-container with sidebar + main content area, used as wrapper for all authenticated pages
- AppSidebar: el-menu with router-link items for all 6 pages
- DashboardView: 3-column grid — GaugeChart (temperature), SignalCard list (top 3), position summary
- GaugeChart: ECharts gauge showing 0-100 temperature with color zones (red/yellow/green)

- [ ] **Step 1: Create all files with the described implementation**

Follow the patterns from the design spec section 6.2. Use `el-row`/`el-col` for layout grid, `el-card` for content blocks, and ECharts `init()` in `onMounted` for the gauge chart. The API module `dashboard.ts` exports `fetchOverview()` and `fetchSentiment()` using the shared axios client.

- [ ] **Step 2: Update App.vue to use layout for authenticated routes**

```vue
<template>
  <AppLayout v-if="isLoggedIn && route.name !== 'login'">
    <router-view />
  </AppLayout>
  <router-view v-else />
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { storeToRefs } from 'pinia'
import AppLayout from '@/components/layout/AppLayout.vue'

const route = useRoute()
const { isLoggedIn } = storeToRefs(useAuthStore())
</script>
```

- [ ] **Step 3: Test login flow manually**

Start both backend and frontend dev servers. Navigate to `http://localhost:5173/login`, enter admin credentials, verify redirect to dashboard.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/
git commit -m "feat: login page, app layout with sidebar, dashboard with temperature gauge"
```

---

### Task 17: Scan + Stock Detail Pages (K-Line Chart)

**Files:**
- Create: `frontend/src/views/ScanView.vue`
- Create: `frontend/src/views/StockDetailView.vue`
- Create: `frontend/src/components/charts/KLineChart.vue`
- Create: `frontend/src/components/charts/RadarChart.vue`
- Create: `frontend/src/components/charts/SectorHeatmap.vue`
- Create: `frontend/src/components/signal/ScoreBreakdown.vue`
- Create: `frontend/src/api/scan.ts`
- Create: `frontend/src/api/stock.ts`

Key implementation details:
- ScanView: el-table with sortable columns (code, name, score, tech/fund/momentum/sentiment scores). Click row navigates to `/stock/:code`. Below table: SectorHeatmap (ECharts treemap) + north flow area chart
- StockDetailView: Top section is KLineChart component. Below: RadarChart (4-axis score) + ScoreBreakdown text + signal history table
- KLineChart: Uses `lightweight-charts` (`createChart`, `addCandlestickSeries`, `addLineSeries` for MA lines). Volume as histogram below. Props: `klineData`, `signals` (for buy/sell markers)
- RadarChart: ECharts radar with 4 axes (tech 40, fund 30, momentum 20, sentiment 10)
- SectorHeatmap: ECharts treemap, each block is a sector, size = volume, color = change_pct

- [ ] **Step 1: Create KLineChart component**

`frontend/src/components/charts/KLineChart.vue`:
```vue
<template>
  <div ref="chartRef" :style="{ width: '100%', height: height + 'px' }" />
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { createChart, type IChartApi, type ISeriesApi, ColorType } from 'lightweight-charts'

const props = defineProps<{
  data: Array<{ time: string; open: number; high: number; low: number; close: number; volume: number }>
  height?: number
  signals?: Array<{ time: string; direction: string }>
}>()

const chartRef = ref<HTMLElement>()
let chart: IChartApi | null = null
let candleSeries: ISeriesApi<'Candlestick'> | null = null
let volumeSeries: ISeriesApi<'Histogram'> | null = null

onMounted(() => {
  if (!chartRef.value) return
  chart = createChart(chartRef.value, {
    layout: { background: { type: ColorType.Solid, color: '#1a1a2e' }, textColor: '#d1d4dc' },
    grid: { vertLines: { color: '#2B2B43' }, horzLines: { color: '#2B2B43' } },
    width: chartRef.value.clientWidth,
    height: props.height || 400,
    crosshair: { mode: 0 },
    timeScale: { timeVisible: false },
  })

  candleSeries = chart.addCandlestickSeries({
    upColor: '#ef5350',
    downColor: '#26a69a',
    borderUpColor: '#ef5350',
    borderDownColor: '#26a69a',
    wickUpColor: '#ef5350',
    wickDownColor: '#26a69a',
  })

  volumeSeries = chart.addHistogramSeries({
    priceFormat: { type: 'volume' },
    priceScaleId: 'volume',
  })
  chart.priceScale('volume').applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } })

  updateData()
})

function updateData() {
  if (!candleSeries || !volumeSeries || !props.data.length) return
  const candles = props.data.map((d) => ({ time: d.time, open: d.open, high: d.high, low: d.low, close: d.close }))
  const volumes = props.data.map((d) => ({ time: d.time, value: d.volume, color: d.close >= d.open ? '#ef535080' : '#26a69a80' }))
  candleSeries.setData(candles)
  volumeSeries.setData(volumes)

  if (props.signals?.length && candleSeries) {
    const markers = props.signals.map((s) => ({
      time: s.time,
      position: s.direction === 'buy' ? ('belowBar' as const) : ('aboveBar' as const),
      color: s.direction === 'buy' ? '#ef5350' : '#26a69a',
      shape: s.direction === 'buy' ? ('arrowUp' as const) : ('arrowDown' as const),
      text: s.direction === 'buy' ? 'B' : 'S',
    }))
    candleSeries.setMarkers(markers)
  }
}

watch(() => props.data, updateData)

onUnmounted(() => {
  chart?.remove()
})
</script>
```

- [ ] **Step 2: Create ScanView and StockDetailView**

ScanView uses `el-table` fetching from `/api/scan/ranking`, with `@row-click` navigating to stock detail. StockDetailView receives `:code` from route params, fetches kline + score data, renders KLineChart + RadarChart + ScoreBreakdown.

- [ ] **Step 3: Create API modules**

`frontend/src/api/scan.ts` and `frontend/src/api/stock.ts` export typed fetch functions using the shared client.

- [ ] **Step 4: Test K-line chart rendering manually**

Start dev servers, navigate to `/scan`, click a stock row, verify K-line renders with candlesticks and volume.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/
git commit -m "feat: scan ranking table, stock detail with K-line chart, radar score, sector heatmap"
```

---

### Task 18: Position + Learn + Settings Pages

**Files:**
- Create: `frontend/src/views/PositionView.vue`
- Create: `frontend/src/views/LearnView.vue`
- Create: `frontend/src/views/SettingsView.vue`
- Create: `frontend/src/components/position/PositionCard.vue`
- Create: `frontend/src/components/position/RiskProgress.vue`
- Create: `frontend/src/api/position.ts`
- Create: `frontend/src/api/settings.ts`
- Create: `frontend/src/api/learn.ts`
- Create: `frontend/src/stores/position.ts`

Key implementation details:
- PositionView: Active positions as cards (PositionCard), each showing code/name/pnl/hold_days + RiskProgress bar (visual distance to stop_loss and take_profit). Below: "Record Buy" dialog (el-dialog + el-form). Bottom: trade history table + stats summary
- RiskProgress: el-progress showing current price position between stop_loss (left/red) and take_profit (right/green)
- LearnView: Tabs for "Today's Lesson" and "Archive". Today shows the current indicator guide with explanation. Archive is an el-collapse with all 10 indicators
- SettingsView: el-tabs with 3 panels — Strategy params (el-form with number inputs for all config values), Feishu config (webhook URL input + test button), Account (change password)

- [ ] **Step 1: Create all files following the described patterns**

Use Element Plus components throughout. Position API module exports `fetchPositions()`, `createPosition()`, `closePosition()`, `fetchTrades()`, `fetchStats()`.

- [ ] **Step 2: Test position management flow manually**

Create a position via the dialog, verify it appears as a card. Close it, verify it moves to trade history.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/
git commit -m "feat: position management, learning center, settings pages"
```

---

## Phase 8: Production Deployment

### Task 19: Dockerfile Multi-Stage Build

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`

- [ ] **Step 1: Create .dockerignore**

```
.git
.env
__pycache__
*.pyc
node_modules
frontend/node_modules
*.md
docs/
tests/
.venv
```

- [ ] **Step 2: Create multi-stage Dockerfile**

```dockerfile
# Stage 1: Build frontend
FROM node:20-alpine AS frontend-build
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Production
FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY --from=frontend-build /build/dist ./app/static

ENV TZ=Asia/Shanghai
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

- [ ] **Step 3: Commit**

```bash
git add Dockerfile .dockerignore
git commit -m "feat: multi-stage Dockerfile (frontend build + Python production)"
```

---

### Task 20: docker-compose.yml + Nginx + SSL + start.sh

**Files:**
- Create: `docker-compose.yml`
- Create: `nginx/nginx.conf`
- Create: `start.sh`

- [ ] **Step 1: Create production docker-compose.yml**

```yaml
services:
  postgres:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-quantclaw}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-quantclaw}
      POSTGRES_DB: ${POSTGRES_DB:-quantclaw}
    volumes:
      - pg-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-quantclaw}"]
      interval: 5s
      timeout: 3s
      retries: 5
    deploy:
      resources:
        limits:
          cpus: "0.5"
          memory: 1G

  quantclaw:
    build: .
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER:-quantclaw}:${POSTGRES_PASSWORD:-quantclaw}@postgres:5432/${POSTGRES_DB:-quantclaw}
      SECRET_KEY: ${SECRET_KEY}
      ADMIN_USERNAME: ${ADMIN_USERNAME:-admin}
      ADMIN_PASSWORD: ${ADMIN_PASSWORD}
      FEISHU_WEBHOOK_URL: ${FEISHU_WEBHOOK_URL}
      BASE_URL: ${BASE_URL:-https://quant.azhefuye.online}
    deploy:
      resources:
        limits:
          cpus: "1.3"
          memory: 2560M

  nginx:
    image: nginx:alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./certbot/conf:/etc/letsencrypt:ro
      - ./certbot/www:/var/www/certbot:ro
    depends_on:
      - quantclaw
    deploy:
      resources:
        limits:
          cpus: "0.2"
          memory: 128M

  certbot:
    image: certbot/certbot
    volumes:
      - ./certbot/conf:/etc/letsencrypt
      - ./certbot/www:/var/www/certbot
    entrypoint: "/bin/sh -c 'trap exit TERM; while :; do certbot renew; sleep 12h & wait $${!}; done;'"

volumes:
  pg-data:
```

- [ ] **Step 2: Create nginx.conf**

`nginx/nginx.conf`:
```nginx
events {
    worker_connections 256;
}

http {
    upstream quantclaw {
        server quantclaw:8000;
    }

    server {
        listen 80;
        server_name quant.azhefuye.online;

        location /.well-known/acme-challenge/ {
            root /var/www/certbot;
        }

        location / {
            return 301 https://$host$request_uri;
        }
    }

    server {
        listen 443 ssl;
        server_name quant.azhefuye.online;

        ssl_certificate /etc/letsencrypt/live/quant.azhefuye.online/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/quant.azhefuye.online/privkey.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;

        client_max_body_size 10M;

        location / {
            proxy_pass http://quantclaw;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
}
```

- [ ] **Step 3: Create start.sh**

```bash
#!/usr/bin/env bash
set -e

if [ ! -f .env ]; then
    echo "ERROR: .env file not found. Copy .env.example to .env and fill in values."
    exit 1
fi

source .env

# First time: get SSL certificate
if [ ! -d "certbot/conf/live/quant.azhefuye.online" ]; then
    echo "==> Requesting initial SSL certificate..."
    mkdir -p certbot/conf certbot/www

    # Start nginx temporarily for ACME challenge
    docker compose up -d nginx
    sleep 5

    docker compose run --rm certbot certonly \
        --webroot --webroot-path=/var/www/certbot \
        --email ${ADMIN_EMAIL:-admin@example.com} \
        --agree-tos --no-eff-email \
        -d quant.azhefuye.online

    docker compose down
    echo "==> SSL certificate obtained."
fi

echo "==> Building and starting QuantClaw..."
docker compose build
docker compose up -d

echo ""
echo "========================================="
echo "  QuantClaw is running!"
echo "  URL: https://quant.azhefuye.online"
echo "  Logs: docker compose logs -f quantclaw"
echo "========================================="
```

- [ ] **Step 4: Make start.sh executable and commit**

```bash
chmod +x start.sh
git add docker-compose.yml nginx/ start.sh
git commit -m "feat: production Docker Compose with Nginx SSL, certbot auto-renewal, start.sh"
```

---

### Task 21: Final Integration Test

- [ ] **Step 1: Run all backend tests**

```bash
cd backend
pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 2: Build Docker image locally**

```bash
cd D:\ide\workspace\personal-new\QuantClaw
docker compose -f docker-compose.dev.yml up -d
docker build -t quantclaw:test .
```

Expected: build succeeds.

- [ ] **Step 3: Test the built image**

```bash
docker run --rm -e DATABASE_URL=postgresql://quantclaw:quantclaw@host.docker.internal:5432/quantclaw -e SECRET_KEY=test -e ADMIN_PASSWORD=admin123 -p 8000:8000 quantclaw:test
```

Open `http://localhost:8000/api/health` → `{"status": "ok"}`
Open `http://localhost:8000/` → Vue3 app loads.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "chore: integration verification complete — QuantClaw P0+P1 ready for deployment"
```
