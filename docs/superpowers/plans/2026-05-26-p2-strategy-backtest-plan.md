# P2: 策略插件化 + 回测系统 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace hardcoded strategy params with configurable strategy templates (4 builtins, user-creatable), and add a backtest engine that simulates any strategy on historical data with full trade logs and performance metrics.

**Architecture:** `StrategyTemplate` DB model stores filter/score/signal/risk configs as JSON columns. `BacktestEngine` runs a day-by-day trading simulation using strategy params and StockDaily data, writing results to `BacktestResult`. Both exposed via REST API and Vue 3 frontend pages.

**Tech Stack:** FastAPI, SQLAlchemy, pandas, ECharts, Vue 3 + TypeScript

---

### Task 1: StrategyTemplate + BacktestResult Models

**Files:**
- Create: `backend/app/models/strategy.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_strategy_model.py`

- [ ] **Step 1: Create strategy models**

```python
# backend/app/models/strategy.py
from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, JSON, Text, func
from app.database import Base


class StrategyTemplate(Base):
    __tablename__ = "strategy_template"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, default="")
    filter_config = Column(JSON, nullable=False)
    score_config = Column(JSON, nullable=False)
    signal_config = Column(JSON, nullable=False)
    risk_config = Column(JSON, nullable=False)
    is_active = Column(Boolean, default=False)
    is_builtin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class BacktestResult(Base):
    __tablename__ = "backtest_result"

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_id = Column(Integer, nullable=False)
    strategy_name = Column(String(100), nullable=False)
    start_date = Column(String(10), nullable=False)
    end_date = Column(String(10), nullable=False)
    initial_capital = Column(Float, nullable=False, default=50000)
    status = Column(String(20), nullable=False, default="running")
    error_message = Column(Text, nullable=True)
    summary = Column(JSON, nullable=True)
    daily_values = Column(JSON, nullable=True)
    trades = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=func.now())
```

- [ ] **Step 2: Register models in __init__.py**

Add to `backend/app/models/__init__.py`:

```python
from app.models.strategy import StrategyTemplate, BacktestResult
```

Add `"StrategyTemplate"` and `"BacktestResult"` to the `__all__` list.

- [ ] **Step 3: Write test**

```python
# backend/tests/test_strategy_model.py
from app.models.strategy import StrategyTemplate, BacktestResult


def test_strategy_template_fields():
    t = StrategyTemplate(
        name="test", description="test strategy",
        filter_config={"min_amount_20d": 50000000},
        score_config={"tech_weight": 0.4},
        signal_config={"min_score": 65},
        risk_config={"stop_loss_pct": -0.05},
        is_active=True, is_builtin=False,
    )
    assert t.name == "test"
    assert t.is_active is True
    assert t.filter_config["min_amount_20d"] == 50000000


def test_backtest_result_fields():
    r = BacktestResult(
        strategy_id=1, strategy_name="test",
        start_date="2025-09-01", end_date="2026-05-26",
        initial_capital=50000, status="running",
    )
    assert r.status == "running"
    assert r.initial_capital == 50000
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_strategy_model.py -v`
Expected: 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/strategy.py backend/app/models/__init__.py backend/tests/test_strategy_model.py
git commit -m "feat: add StrategyTemplate and BacktestResult models"
```

---

### Task 2: Strategy Schemas + CRUD API

**Files:**
- Create: `backend/app/schemas/strategy.py`
- Create: `backend/app/api/strategy.py`
- Modify: `backend/app/api/__init__.py`

- [ ] **Step 1: Create schemas**

```python
# backend/app/schemas/strategy.py
from pydantic import BaseModel
from datetime import datetime


class FilterConfig(BaseModel):
    min_amount_20d: int = 50_000_000
    max_price: float = 50
    min_list_days: int = 60
    exclude_bj: bool = True


class ScoreConfig(BaseModel):
    tech_weight: float = 0.4
    fund_weight: float = 0.3
    momentum_weight: float = 0.2
    sentiment_weight: float = 0.1
    ma_periods: list[int] = [5, 10, 20]
    macd_enabled: bool = True
    kdj_enabled: bool = True
    bollinger_enabled: bool = True
    volume_ratio_threshold: float = 1.5


class SignalConfig(BaseModel):
    min_score: int = 65
    top_n: int = 3
    concentration_control: bool = True


class RiskConfig(BaseModel):
    stop_loss_pct: float = -0.05
    take_profit_pct: float = 0.12
    trailing_trigger: float = 0.07
    trailing_drawdown: float = 0.03
    max_hold_days: int = 5


class StrategyCreate(BaseModel):
    name: str
    description: str = ""
    filter_config: FilterConfig = FilterConfig()
    score_config: ScoreConfig = ScoreConfig()
    signal_config: SignalConfig = SignalConfig()
    risk_config: RiskConfig = RiskConfig()


class StrategyUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    filter_config: FilterConfig | None = None
    score_config: ScoreConfig | None = None
    signal_config: SignalConfig | None = None
    risk_config: RiskConfig | None = None


class StrategyOut(BaseModel):
    id: int
    name: str
    description: str
    filter_config: dict
    score_config: dict
    signal_config: dict
    risk_config: dict
    is_active: bool
    is_builtin: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True
```

- [ ] **Step 2: Create strategy API router**

```python
# backend/app/api/strategy.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.strategy import StrategyTemplate
from app.models.system import User
from app.schemas.strategy import StrategyCreate, StrategyUpdate, StrategyOut

router = APIRouter(prefix="/api/strategies", tags=["strategies"])


@router.get("", response_model=list[StrategyOut])
def list_strategies(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(StrategyTemplate).order_by(StrategyTemplate.is_active.desc(), StrategyTemplate.id).all()


@router.post("", response_model=StrategyOut, status_code=201)
def create_strategy(body: StrategyCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = StrategyTemplate(
        name=body.name, description=body.description,
        filter_config=body.filter_config.model_dump(),
        score_config=body.score_config.model_dump(),
        signal_config=body.signal_config.model_dump(),
        risk_config=body.risk_config.model_dump(),
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


@router.get("/{strategy_id}", response_model=StrategyOut)
def get_strategy(strategy_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = db.query(StrategyTemplate).filter(StrategyTemplate.id == strategy_id).first()
    if not t:
        raise HTTPException(404, "Strategy not found")
    return t


@router.put("/{strategy_id}", response_model=StrategyOut)
def update_strategy(strategy_id: int, body: StrategyUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = db.query(StrategyTemplate).filter(StrategyTemplate.id == strategy_id).first()
    if not t:
        raise HTTPException(404, "Strategy not found")
    if body.name is not None:
        t.name = body.name
    if body.description is not None:
        t.description = body.description
    if body.filter_config is not None:
        t.filter_config = body.filter_config.model_dump()
    if body.score_config is not None:
        t.score_config = body.score_config.model_dump()
    if body.signal_config is not None:
        t.signal_config = body.signal_config.model_dump()
    if body.risk_config is not None:
        t.risk_config = body.risk_config.model_dump()
    db.commit()
    db.refresh(t)
    return t


@router.delete("/{strategy_id}")
def delete_strategy(strategy_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = db.query(StrategyTemplate).filter(StrategyTemplate.id == strategy_id).first()
    if not t:
        raise HTTPException(404, "Strategy not found")
    if t.is_builtin:
        raise HTTPException(400, "Cannot delete builtin strategy")
    db.delete(t)
    db.commit()
    return {"ok": True}


@router.put("/{strategy_id}/activate", response_model=StrategyOut)
def activate_strategy(strategy_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = db.query(StrategyTemplate).filter(StrategyTemplate.id == strategy_id).first()
    if not t:
        raise HTTPException(404, "Strategy not found")
    db.query(StrategyTemplate).update({"is_active": False})
    t.is_active = True
    db.commit()
    db.refresh(t)
    return t
```

- [ ] **Step 3: Register router in api/__init__.py**

Add to `backend/app/api/__init__.py`:

```python
from app.api.strategy import router as strategy_router
```

Add: `api_router.include_router(strategy_router)`

- [ ] **Step 4: Quick import check**

Run: `cd backend && python -c "from app.api.strategy import router; print('OK')"`

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/strategy.py backend/app/api/strategy.py backend/app/api/__init__.py
git commit -m "feat: add strategy template CRUD API"
```

---

### Task 3: Seed Builtin Strategies

**Files:**
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_builtin_strategies.py`

- [ ] **Step 1: Add seed function to main.py**

Read `backend/app/main.py` first. Add import at top:

```python
from app.models.strategy import StrategyTemplate
```

Add this function after `_seed_admin()`:

```python
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
```

In the `lifespan` function, call `_seed_strategies()` after `_seed_admin()`.

- [ ] **Step 2: Write test**

```python
# backend/tests/test_builtin_strategies.py
from app.main import BUILTIN_STRATEGIES


def test_builtin_strategies_count():
    assert len(BUILTIN_STRATEGIES) == 4


def test_exactly_one_active():
    active = [s for s in BUILTIN_STRATEGIES if s["is_active"]]
    assert len(active) == 1
    assert active[0]["name"] == "稳健短线"


def test_all_have_required_keys():
    required = {"name", "description", "filter_config", "score_config", "signal_config", "risk_config"}
    for s in BUILTIN_STRATEGIES:
        assert required.issubset(s.keys()), f"Missing keys in {s['name']}"


def test_weights_sum_to_one():
    for s in BUILTIN_STRATEGIES:
        sc = s["score_config"]
        total = sc["tech_weight"] + sc["fund_weight"] + sc["momentum_weight"] + sc["sentiment_weight"]
        assert abs(total - 1.0) < 0.01, f"Weights don't sum to 1.0 in {s['name']}: {total}"
```

- [ ] **Step 3: Run tests**

Run: `cd backend && python -m pytest tests/test_builtin_strategies.py -v`
Expected: 4 tests PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/main.py backend/tests/test_builtin_strategies.py
git commit -m "feat: seed 4 builtin strategy templates at startup"
```

---

### Task 4: Refactor Scoring + job_post_market_analyze

**Files:**
- Modify: `backend/app/services/strategy/scoring.py`
- Modify: `backend/app/scheduler/jobs.py`
- Test: `backend/tests/test_weighted_scoring.py`

- [ ] **Step 1: Refactor compute_total_score to support weights**

Read `backend/app/services/strategy/scoring.py`. Replace the `compute_total_score` function at the bottom:

```python
def compute_total_score(raw_scores: dict, weights: dict | None = None) -> int:
    if weights is None:
        return raw_scores["tech"] + raw_scores["fund"] + raw_scores["momentum"] + raw_scores["sentiment"]
    max_scores = {"tech": 40, "fund": 30, "momentum": 20, "sentiment": 10}
    total = 0.0
    for key in ["tech", "fund", "momentum", "sentiment"]:
        w = weights.get(f"{key}_weight", 0.25)
        normalized = raw_scores[key] / max_scores[key] if max_scores[key] > 0 else 0
        total += normalized * w
    return int(round(total * 100))
```

- [ ] **Step 2: Write test**

```python
# backend/tests/test_weighted_scoring.py
from app.services.strategy.scoring import compute_total_score


def test_default_weights_backward_compatible():
    scores = {"tech": 30, "fund": 20, "momentum": 15, "sentiment": 8}
    result = compute_total_score(scores)
    assert result == 73


def test_weighted_scoring():
    scores = {"tech": 40, "fund": 0, "momentum": 0, "sentiment": 0}
    weights = {"tech_weight": 1.0, "fund_weight": 0.0, "momentum_weight": 0.0, "sentiment_weight": 0.0}
    result = compute_total_score(scores, weights)
    assert result == 100


def test_balanced_weights():
    scores = {"tech": 20, "fund": 15, "momentum": 10, "sentiment": 5}
    weights = {"tech_weight": 0.25, "fund_weight": 0.25, "momentum_weight": 0.25, "sentiment_weight": 0.25}
    result = compute_total_score(scores, weights)
    assert result == 50
```

- [ ] **Step 3: Run scoring tests**

Run: `cd backend && python -m pytest tests/test_weighted_scoring.py -v`
Expected: 3 tests PASS

- [ ] **Step 4: Refactor job_post_market_analyze**

Read `backend/app/scheduler/jobs.py`. In `job_post_market_analyze()`:

a) At the top of the function, replace the DEFAULT_STRATEGY loading and `StrategyConfig` query block with:

```python
        from app.models.strategy import StrategyTemplate
        active = db.query(StrategyTemplate).filter(StrategyTemplate.is_active == True).first()
        if not active:
            logger.warning("No active strategy template, using defaults")
            filter_cfg = {"min_amount_20d": 50_000_000, "max_price": 50, "min_list_days": 60}
            score_cfg = {"tech_weight": 0.4, "fund_weight": 0.3, "momentum_weight": 0.2, "sentiment_weight": 0.1}
            signal_cfg = {"min_score": 65, "top_n": 3, "concentration_control": True}
            risk_cfg = {"stop_loss_pct": -0.05, "take_profit_pct": 0.12, "trailing_trigger": 0.07, "trailing_drawdown": 0.03, "max_hold_days": 5}
        else:
            filter_cfg = active.filter_config
            score_cfg = active.score_config
            signal_cfg = active.signal_config
            risk_cfg = active.risk_config
```

b) Where `total` score is computed (the line that sums tech_score + fund_score + momentum_score + sentiment_score), replace with:

```python
                total = compute_total_score(
                    {"tech": tech_score, "fund": fund_score, "momentum": momentum_score, "sentiment": sentiment_score},
                    score_cfg,
                )
```

c) Where `select_top_n` is called, use `signal_cfg`:

```python
            top = select_top_n(scored_df, min_score=signal_cfg.get("min_score", 65), top_n=signal_cfg.get("top_n", 3))
```

d) Where `RiskConfig` is used, use `risk_cfg` values:

```python
                from app.services.position.risk import check_sell_signals, RiskConfig
                cfg = RiskConfig(
                    stop_loss_pct=risk_cfg.get("stop_loss_pct", -0.05),
                    take_profit_pct=risk_cfg.get("take_profit_pct", 0.12),
                    trailing_trigger=risk_cfg.get("trailing_trigger", 0.07),
                    trailing_drawdown=risk_cfg.get("trailing_drawdown", 0.03),
                    max_hold_days=risk_cfg.get("max_hold_days", 5),
                )
```

- [ ] **Step 5: Run full test suite**

Run: `cd backend && python -m pytest -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/strategy/scoring.py backend/app/scheduler/jobs.py backend/tests/test_weighted_scoring.py
git commit -m "refactor: job_post_market_analyze uses active StrategyTemplate with weighted scoring"
```

---

### Task 5: Backtest Engine

**Files:**
- Create: `backend/app/services/backtest/__init__.py`
- Create: `backend/app/services/backtest/engine.py`
- Test: `backend/tests/test_backtest_engine.py`

- [ ] **Step 1: Create __init__.py**

```python
# backend/app/services/backtest/__init__.py
```

- [ ] **Step 2: Write failing test**

```python
# backend/tests/test_backtest_engine.py
import pandas as pd
from datetime import date
from app.services.backtest.engine import BacktestEngine


def _make_klines(code: str, days: int, base_price: float = 10.0):
    """Generate simple ascending K-line data."""
    records = []
    d = date(2026, 1, 5)
    for i in range(days):
        while d.weekday() >= 5:
            d = date.fromordinal(d.toordinal() + 1)
        price = base_price + i * 0.1
        records.append({
            "code": code, "trade_date": d,
            "open": price, "high": price + 0.2, "low": price - 0.1,
            "close": price, "volume": 50_000_000, "amount": price * 50_000_000,
            "change_pct": 1.0,
        })
        d = date.fromordinal(d.toordinal() + 1)
    return records


def test_engine_runs_and_returns_result():
    klines = _make_klines("000001", 60) + _make_klines("600000", 60)
    kline_df = pd.DataFrame(klines)
    stocks_df = pd.DataFrame([
        {"code": "000001", "name": "Test A", "market": "sz", "is_st": False, "list_date": date(2020, 1, 1), "industry": "银行"},
        {"code": "600000", "name": "Test B", "market": "sh", "is_st": False, "list_date": date(2020, 1, 1), "industry": "银行"},
    ])
    strategy_config = {
        "filter_config": {"min_amount_20d": 1, "max_price": 9999, "min_list_days": 1, "exclude_bj": True},
        "score_config": {"tech_weight": 0.4, "fund_weight": 0.3, "momentum_weight": 0.2, "sentiment_weight": 0.1},
        "signal_config": {"min_score": 0, "top_n": 2, "concentration_control": False},
        "risk_config": {"stop_loss_pct": -0.05, "take_profit_pct": 0.12, "max_hold_days": 5, "trailing_trigger": 0.07, "trailing_drawdown": 0.03},
    }
    engine = BacktestEngine(
        stocks_df=stocks_df, kline_df=kline_df,
        strategy_config=strategy_config,
        start_date=date(2026, 2, 2), end_date=date(2026, 3, 20),
        initial_capital=50000,
    )
    result = engine.run()
    assert "total_return" in result["summary"]
    assert "max_drawdown" in result["summary"]
    assert "win_rate" in result["summary"]
    assert len(result["daily_values"]) > 0
    assert isinstance(result["trades"], list)


def test_engine_stop_loss():
    """Create data where price drops to trigger stop loss."""
    records = []
    d = date(2026, 2, 2)
    for i in range(30):
        while d.weekday() >= 5:
            d = date.fromordinal(d.toordinal() + 1)
        price = 10.0 - i * 0.3 if i > 0 else 10.0
        records.append({
            "code": "000001", "trade_date": d,
            "open": price, "high": price + 0.1, "low": price - 0.1,
            "close": max(price, 1.0), "volume": 50_000_000, "amount": 500_000_000,
            "change_pct": -3.0,
        })
        d = date.fromordinal(d.toordinal() + 1)
    kline_df = pd.DataFrame(records)
    stocks_df = pd.DataFrame([
        {"code": "000001", "name": "Loser", "market": "sz", "is_st": False, "list_date": date(2020, 1, 1), "industry": "银行"},
    ])
    config = {
        "filter_config": {"min_amount_20d": 1, "max_price": 9999, "min_list_days": 1, "exclude_bj": True},
        "score_config": {"tech_weight": 0.25, "fund_weight": 0.25, "momentum_weight": 0.25, "sentiment_weight": 0.25},
        "signal_config": {"min_score": 0, "top_n": 1, "concentration_control": False},
        "risk_config": {"stop_loss_pct": -0.05, "take_profit_pct": 0.50, "max_hold_days": 30, "trailing_trigger": 0.5, "trailing_drawdown": 0.3},
    }
    engine = BacktestEngine(
        stocks_df=stocks_df, kline_df=kline_df,
        strategy_config=config,
        start_date=date(2026, 2, 2), end_date=date(2026, 3, 15),
        initial_capital=50000,
    )
    result = engine.run()
    assert result["summary"]["total_return"] < 0
    sells_with_stop = [t for t in result["trades"] if t.get("sell_reason") == "stop_loss"]
    assert len(sells_with_stop) > 0
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_backtest_engine.py -v`
Expected: FAIL — module not found

- [ ] **Step 4: Implement BacktestEngine**

```python
# backend/app/services/backtest/engine.py
import logging
from datetime import date
from dataclasses import dataclass, field

import pandas as pd
import numpy as np

from app.services.data.indicators import calc_ma, calc_macd, calc_volume_ratio
from app.services.strategy.scoring import score_technical, score_fund, score_momentum, score_sentiment, compute_total_score

logger = logging.getLogger(__name__)


@dataclass
class _Position:
    code: str
    name: str
    buy_date: date
    buy_price: float
    shares: int
    highest_price: float = 0.0

    def __post_init__(self):
        self.highest_price = self.buy_price


class BacktestEngine:
    def __init__(
        self,
        stocks_df: pd.DataFrame,
        kline_df: pd.DataFrame,
        strategy_config: dict,
        start_date: date,
        end_date: date,
        initial_capital: float = 50000,
        benchmark_code: str = "000001",
    ):
        self.stocks_df = stocks_df
        self.kline_df = kline_df
        self.config = strategy_config
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.benchmark_code = benchmark_code

        self.cash = initial_capital
        self.positions: list[_Position] = []
        self.trades: list[dict] = []
        self.daily_values: list[dict] = []

    def _get_trade_dates(self) -> list[date]:
        dates = sorted(self.kline_df["trade_date"].unique())
        return [d for d in dates if self.start_date <= d <= self.end_date]

    def _get_day_data(self, trade_date: date) -> pd.DataFrame:
        return self.kline_df[self.kline_df["trade_date"] == trade_date]

    def _get_kline_window(self, code: str, trade_date: date, window: int = 30) -> pd.DataFrame:
        stock_data = self.kline_df[
            (self.kline_df["code"] == code) & (self.kline_df["trade_date"] <= trade_date)
        ].sort_values("trade_date").tail(window)
        return stock_data

    def _score_stock(self, code: str, trade_date: date) -> int | None:
        klines = self._get_kline_window(code, trade_date, 30)
        if len(klines) < 20:
            return None
        kline_df = klines[["open", "high", "low", "close", "volume"]].reset_index(drop=True)
        tech_score, _ = score_technical(kline_df)
        vol_ratio = calc_volume_ratio(kline_df["volume"], 20) if len(kline_df) >= 21 else 1.0
        fund_score, _ = score_fund({"north_net_3d": 0, "main_net": 0, "super_large_pct": 0, "volume_ratio": vol_ratio})
        pct_5d = 0
        if len(klines) >= 5:
            pct_5d = (klines.iloc[-1]["close"] - klines.iloc[-5]["close"]) / klines.iloc[-5]["close"] * 100
        momentum_score, _ = score_momentum({
            "pct_5d": pct_5d, "relative_strength": pct_5d,
            "is_20d_high": klines.iloc[-1]["close"] >= klines["close"].tail(20).max(),
        })
        sentiment_score, _ = score_sentiment({"sector_rank_pct": 50, "limit_up": 40, "limit_down": 15, "sector_net_flow": 0})
        score_cfg = self.config.get("score_config")
        total = compute_total_score(
            {"tech": tech_score, "fund": fund_score, "momentum": momentum_score, "sentiment": sentiment_score},
            score_cfg,
        )
        return total

    def _check_sell(self, pos: _Position, current_price: float, trade_date: date) -> str | None:
        risk = self.config.get("risk_config", {})
        pnl_pct = (current_price - pos.buy_price) / pos.buy_price
        if pnl_pct <= risk.get("stop_loss_pct", -0.05):
            return "stop_loss"
        if pnl_pct >= risk.get("take_profit_pct", 0.12):
            return "take_profit"
        hold_days = (trade_date - pos.buy_date).days
        if hold_days >= risk.get("max_hold_days", 5):
            return "max_hold_days"
        if pos.highest_price > pos.buy_price:
            gain_from_buy = (pos.highest_price - pos.buy_price) / pos.buy_price
            if gain_from_buy >= risk.get("trailing_trigger", 0.07):
                drawdown = (pos.highest_price - current_price) / pos.highest_price
                if drawdown >= risk.get("trailing_drawdown", 0.03):
                    return "trailing_stop"
        return None

    def _portfolio_value(self, day_data: pd.DataFrame) -> float:
        price_map = dict(zip(day_data["code"], day_data["close"]))
        stock_value = sum(price_map.get(p.code, p.buy_price) * p.shares for p in self.positions)
        return self.cash + stock_value

    def run(self) -> dict:
        trade_dates = self._get_trade_dates()
        if not trade_dates:
            return {"summary": {}, "daily_values": [], "trades": []}

        signal_cfg = self.config.get("signal_config", {})
        max_positions = signal_cfg.get("top_n", 3)
        peak_value = self.initial_capital
        max_drawdown = 0.0

        for td in trade_dates:
            day_data = self._get_day_data(td)
            if day_data.empty:
                continue
            price_map = dict(zip(day_data["code"], day_data["close"]))

            # Update highest prices
            for pos in self.positions:
                cp = price_map.get(pos.code, pos.buy_price)
                if cp > pos.highest_price:
                    pos.highest_price = cp

            # Check sells
            to_sell = []
            for pos in self.positions:
                cp = price_map.get(pos.code)
                if cp is None:
                    continue
                reason = self._check_sell(pos, cp, td)
                if reason:
                    to_sell.append((pos, cp, reason))

            for pos, sell_price, reason in to_sell:
                pnl = (sell_price - pos.buy_price) * pos.shares
                self.cash += sell_price * pos.shares
                self.trades.append({
                    "code": pos.code, "name": pos.name,
                    "buy_date": pos.buy_date.isoformat(), "buy_price": round(pos.buy_price, 2),
                    "sell_date": td.isoformat(), "sell_price": round(sell_price, 2),
                    "shares": pos.shares, "pnl": round(pnl, 2),
                    "pnl_pct": round((sell_price - pos.buy_price) / pos.buy_price * 100, 2),
                    "hold_days": (td - pos.buy_date).days, "sell_reason": reason,
                })
                self.positions.remove(pos)

            # Check buys
            if len(self.positions) < max_positions:
                available_codes = set(price_map.keys()) - {p.code for p in self.positions}
                scored = []
                for code in available_codes:
                    s = self._score_stock(code, td)
                    if s is not None and s >= signal_cfg.get("min_score", 65):
                        name_row = self.stocks_df[self.stocks_df["code"] == code]
                        name = name_row.iloc[0]["name"] if not name_row.empty else code
                        scored.append((code, name, s, price_map[code]))
                scored.sort(key=lambda x: x[2], reverse=True)

                slots = max_positions - len(self.positions)
                for code, name, score, buy_price in scored[:slots]:
                    if buy_price <= 0:
                        continue
                    per_position = self.cash / (slots - len([1 for _ in range(slots)]) + 1) if slots > 0 else self.cash
                    per_position = min(per_position, self.cash * 0.95)
                    shares = int(per_position / buy_price / 100) * 100
                    if shares <= 0:
                        continue
                    cost = buy_price * shares
                    if cost > self.cash:
                        continue
                    self.cash -= cost
                    self.positions.append(_Position(code=code, name=name, buy_date=td, buy_price=buy_price, shares=shares))

            # Record daily value
            portfolio_val = self._portfolio_value(day_data)
            if portfolio_val > peak_value:
                peak_value = portfolio_val
            dd = (peak_value - portfolio_val) / peak_value if peak_value > 0 else 0
            if dd > max_drawdown:
                max_drawdown = dd

            self.daily_values.append({"date": td.isoformat(), "value": round(portfolio_val, 2)})

        # Compute summary
        final_value = self.daily_values[-1]["value"] if self.daily_values else self.initial_capital
        total_return = (final_value - self.initial_capital) / self.initial_capital
        trading_days = len(self.daily_values)
        annual_return = total_return * (250 / trading_days) if trading_days > 0 else 0

        wins = [t for t in self.trades if t["pnl"] > 0]
        losses = [t for t in self.trades if t["pnl"] <= 0]
        win_rate = len(wins) / len(self.trades) if self.trades else 0
        avg_win = sum(t["pnl"] for t in wins) / len(wins) if wins else 0
        avg_loss = abs(sum(t["pnl"] for t in losses) / len(losses)) if losses else 1
        profit_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0

        # Sharpe ratio
        if len(self.daily_values) >= 2:
            values = [d["value"] for d in self.daily_values]
            returns = [(values[i] - values[i-1]) / values[i-1] for i in range(1, len(values))]
            avg_ret = np.mean(returns)
            std_ret = np.std(returns)
            sharpe = (avg_ret / std_ret) * np.sqrt(250) if std_ret > 0 else 0
        else:
            sharpe = 0

        summary = {
            "total_return": round(total_return, 4),
            "annual_return": round(annual_return, 4),
            "max_drawdown": round(-max_drawdown, 4),
            "win_rate": round(win_rate, 4),
            "sharpe_ratio": round(float(sharpe), 2),
            "profit_loss_ratio": round(profit_loss_ratio, 2),
            "total_trades": len(self.trades),
            "final_value": round(final_value, 2),
        }
        return {"summary": summary, "daily_values": self.daily_values, "trades": self.trades}
```

- [ ] **Step 5: Run tests**

Run: `cd backend && python -m pytest tests/test_backtest_engine.py -v`
Expected: 2 tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/backtest/ backend/tests/test_backtest_engine.py
git commit -m "feat: add BacktestEngine with day-by-day trading simulation"
```

---

### Task 6: Backtest API

**Files:**
- Create: `backend/app/schemas/backtest.py`
- Create: `backend/app/api/backtest.py`
- Modify: `backend/app/api/__init__.py`

- [ ] **Step 1: Create backtest schemas**

```python
# backend/app/schemas/backtest.py
from pydantic import BaseModel
from datetime import datetime


class BacktestRequest(BaseModel):
    strategy_id: int
    start_date: str
    end_date: str
    initial_capital: float = 50000


class BacktestOut(BaseModel):
    id: int
    strategy_id: int
    strategy_name: str
    start_date: str
    end_date: str
    initial_capital: float
    status: str
    error_message: str | None = None
    summary: dict | None = None
    daily_values: list | None = None
    trades: list | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True
```

- [ ] **Step 2: Create backtest API**

```python
# backend/app/api/backtest.py
import threading
import logging
from datetime import date, timedelta

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.database import SessionLocal
from app.models.stock import StockBasic, StockDaily
from app.models.strategy import StrategyTemplate, BacktestResult
from app.models.system import User
from app.schemas.backtest import BacktestRequest, BacktestOut
from app.services.backtest.engine import BacktestEngine
from app.services.data.fetcher import fetch_daily_klines_batch

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


def _run_backtest(backtest_id: int, strategy: dict, start_date: str, end_date: str, initial_capital: float):
    db = SessionLocal()
    try:
        bt = db.query(BacktestResult).filter(BacktestResult.id == backtest_id).first()
        if not bt:
            return

        start_d = date.fromisoformat(start_date)
        end_d = date.fromisoformat(end_date)

        stocks = db.query(StockBasic).all()
        stocks_df = pd.DataFrame([
            {"code": s.code, "name": s.name, "market": s.market, "is_st": s.is_st,
             "list_date": s.list_date or date(2020, 1, 1), "industry": s.industry or ""}
            for s in stocks
        ])

        if stocks_df.empty:
            bt.status = "failed"
            bt.error_message = "No stock data in database. Run seed_data first."
            db.commit()
            return

        fetch_start = (start_d - timedelta(days=60)).strftime("%Y%m%d")
        fetch_end = end_d.strftime("%Y%m%d")

        klines = db.query(StockDaily).filter(
            StockDaily.trade_date >= start_d - timedelta(days=60),
            StockDaily.trade_date <= end_d,
        ).all()

        if not klines:
            bt.status = "failed"
            bt.error_message = "No K-line data available for the selected date range."
            db.commit()
            return

        kline_df = pd.DataFrame([
            {"code": k.code, "trade_date": k.trade_date, "open": k.open, "high": k.high,
             "low": k.low, "close": k.close, "volume": k.volume, "amount": k.amount,
             "change_pct": k.change_pct or 0}
            for k in klines
        ])

        engine = BacktestEngine(
            stocks_df=stocks_df, kline_df=kline_df,
            strategy_config=strategy,
            start_date=start_d, end_date=end_d,
            initial_capital=initial_capital,
        )
        result = engine.run()

        bt.status = "completed"
        bt.summary = result["summary"]
        bt.daily_values = result["daily_values"]
        bt.trades = result["trades"]
        db.commit()

    except Exception as e:
        logger.error(f"Backtest {backtest_id} failed: {e}")
        try:
            bt = db.query(BacktestResult).filter(BacktestResult.id == backtest_id).first()
            if bt:
                bt.status = "failed"
                bt.error_message = str(e)
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


@router.post("/run", response_model=BacktestOut, status_code=201)
def run_backtest(body: BacktestRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    strategy = db.query(StrategyTemplate).filter(StrategyTemplate.id == body.strategy_id).first()
    if not strategy:
        raise HTTPException(404, "Strategy not found")

    bt = BacktestResult(
        strategy_id=strategy.id,
        strategy_name=strategy.name,
        start_date=body.start_date,
        end_date=body.end_date,
        initial_capital=body.initial_capital,
        status="running",
    )
    db.add(bt)
    db.commit()
    db.refresh(bt)

    strategy_config = {
        "filter_config": strategy.filter_config,
        "score_config": strategy.score_config,
        "signal_config": strategy.signal_config,
        "risk_config": strategy.risk_config,
    }

    thread = threading.Thread(
        target=_run_backtest,
        args=(bt.id, strategy_config, body.start_date, body.end_date, body.initial_capital),
        daemon=True,
    )
    thread.start()

    return bt


@router.get("/list", response_model=list[BacktestOut])
def list_backtests(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(BacktestResult).order_by(BacktestResult.id.desc()).limit(20).all()


@router.get("/{backtest_id}", response_model=BacktestOut)
def get_backtest(backtest_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    bt = db.query(BacktestResult).filter(BacktestResult.id == backtest_id).first()
    if not bt:
        raise HTTPException(404, "Backtest not found")
    return bt


@router.delete("/{backtest_id}")
def delete_backtest(backtest_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    bt = db.query(BacktestResult).filter(BacktestResult.id == backtest_id).first()
    if not bt:
        raise HTTPException(404, "Backtest not found")
    db.delete(bt)
    db.commit()
    return {"ok": True}
```

- [ ] **Step 3: Register router**

Add to `backend/app/api/__init__.py`:

```python
from app.api.backtest import router as backtest_router
```

Add: `api_router.include_router(backtest_router)`

- [ ] **Step 4: Quick import check**

Run: `cd backend && python -c "from app.api.backtest import router; print('OK')"`

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/backtest.py backend/app/api/backtest.py backend/app/api/__init__.py
git commit -m "feat: add backtest API with async execution"
```

---

### Task 7: Frontend Strategy API + Management UI

**Files:**
- Create: `frontend/src/api/strategy.ts`
- Modify: `frontend/src/views/SettingsView.vue`

- [ ] **Step 1: Create strategy API module**

```typescript
// frontend/src/api/strategy.ts
import client from './client'

export interface StrategyTemplate {
  id: number
  name: string
  description: string
  filter_config: Record<string, any>
  score_config: Record<string, any>
  signal_config: Record<string, any>
  risk_config: Record<string, any>
  is_active: boolean
  is_builtin: boolean
  created_at?: string
  updated_at?: string
}

export function listStrategies() {
  return client.get<StrategyTemplate[]>('/strategies')
}

export function getStrategy(id: number) {
  return client.get<StrategyTemplate>(`/strategies/${id}`)
}

export function createStrategy(data: Partial<StrategyTemplate>) {
  return client.post<StrategyTemplate>('/strategies', data)
}

export function updateStrategy(id: number, data: Partial<StrategyTemplate>) {
  return client.put<StrategyTemplate>(`/strategies/${id}`, data)
}

export function deleteStrategy(id: number) {
  return client.delete(`/strategies/${id}`)
}

export function activateStrategy(id: number) {
  return client.put<StrategyTemplate>(`/strategies/${id}/activate`)
}
```

- [ ] **Step 2: Add strategy management to SettingsView.vue**

Read `frontend/src/views/SettingsView.vue` first. This is a significant modification. You need to:

a) Import the strategy API:
```typescript
import { listStrategies, activateStrategy, createStrategy, deleteStrategy, type StrategyTemplate } from '@/api/strategy'
```

b) Add reactive state:
```typescript
const strategies = ref<StrategyTemplate[]>([])
const showStrategyEditor = ref(false)
const editingStrategy = ref<StrategyTemplate | null>(null)
```

c) Add functions:
```typescript
async function loadStrategies() {
  try {
    const { data } = await listStrategies()
    strategies.value = data
  } catch {}
}

async function onActivate(id: number) {
  await activateStrategy(id)
  await loadStrategies()
}

async function onDuplicate(strategy: StrategyTemplate) {
  await createStrategy({
    name: strategy.name + ' (副本)',
    description: strategy.description,
    filter_config: strategy.filter_config,
    score_config: strategy.score_config,
    signal_config: strategy.signal_config,
    risk_config: strategy.risk_config,
  })
  await loadStrategies()
}

async function onDeleteStrategy(id: number) {
  await deleteStrategy(id)
  await loadStrategies()
}
```

d) Call `loadStrategies()` in `onMounted`.

e) Add a "策略管理" section in the template, AFTER the data source card and BEFORE the existing strategy parameters section. Show strategy cards in a grid:

```vue
<div class="card settings-card">
  <div class="settings-header">
    <h3 class="settings-title">策略管理</h3>
  </div>
  <div class="strategy-grid">
    <div v-for="s in strategies" :key="s.id" class="strategy-card" :class="{ active: s.is_active }">
      <div class="strat-header">
        <span class="strat-name">{{ s.name }}</span>
        <span v-if="s.is_active" class="strat-badge">当前激活</span>
      </div>
      <p class="strat-desc">{{ s.description }}</p>
      <div class="strat-weights">
        <span>技{{ (s.score_config.tech_weight * 100).toFixed(0) }}</span>
        <span>资{{ (s.score_config.fund_weight * 100).toFixed(0) }}</span>
        <span>动{{ (s.score_config.momentum_weight * 100).toFixed(0) }}</span>
        <span>情{{ (s.score_config.sentiment_weight * 100).toFixed(0) }}</span>
      </div>
      <div class="strat-actions">
        <button v-if="!s.is_active" class="btn-sm" @click="onActivate(s.id)">激活</button>
        <button class="btn-sm" @click="onDuplicate(s)">复制</button>
        <button v-if="!s.is_builtin" class="btn-sm btn-danger" @click="onDeleteStrategy(s.id)">删除</button>
      </div>
    </div>
  </div>
</div>
```

f) Add matching CSS for `.strategy-grid`, `.strategy-card`, `.strat-*` classes following the existing dark theme pattern.

- [ ] **Step 3: Verify in browser**

Start dev server, go to Settings. Verify strategy cards appear, activate/duplicate/delete work.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/strategy.ts frontend/src/views/SettingsView.vue
git commit -m "feat: add strategy management UI in settings page"
```

---

### Task 8: Frontend Backtest API + Page

**Files:**
- Create: `frontend/src/api/backtest.ts`
- Create: `frontend/src/views/BacktestView.vue`

- [ ] **Step 1: Create backtest API module**

```typescript
// frontend/src/api/backtest.ts
import client from './client'

export interface BacktestRequest {
  strategy_id: number
  start_date: string
  end_date: string
  initial_capital: number
}

export interface BacktestTrade {
  code: string
  name: string
  buy_date: string
  buy_price: number
  sell_date: string
  sell_price: number
  shares: number
  pnl: number
  pnl_pct: number
  hold_days: number
  sell_reason: string
}

export interface BacktestSummary {
  total_return: number
  annual_return: number
  max_drawdown: number
  win_rate: number
  sharpe_ratio: number
  profit_loss_ratio: number
  total_trades: number
  final_value: number
}

export interface BacktestResult {
  id: number
  strategy_id: number
  strategy_name: string
  start_date: string
  end_date: string
  initial_capital: number
  status: string
  error_message?: string
  summary?: BacktestSummary
  daily_values?: { date: string; value: number }[]
  trades?: BacktestTrade[]
  created_at?: string
}

export function runBacktest(data: BacktestRequest) {
  return client.post<BacktestResult>('/backtest/run', data)
}

export function getBacktest(id: number) {
  return client.get<BacktestResult>(`/backtest/${id}`)
}

export function listBacktests() {
  return client.get<BacktestResult[]>('/backtest/list')
}

export function deleteBacktest(id: number) {
  return client.delete(`/backtest/${id}`)
}
```

- [ ] **Step 2: Create BacktestView.vue**

```vue
<!-- frontend/src/views/BacktestView.vue -->
<template>
  <div class="backtest-page">
    <h1 class="page-title">策略回测</h1>

    <!-- Config panel -->
    <div class="card config-panel">
      <div class="config-row">
        <div class="config-field">
          <label>策略</label>
          <select v-model="form.strategy_id" class="form-select">
            <option v-for="s in strategies" :key="s.id" :value="s.id">{{ s.name }}</option>
          </select>
        </div>
        <div class="config-field">
          <label>开始日期</label>
          <input type="date" v-model="form.start_date" class="form-input" />
        </div>
        <div class="config-field">
          <label>结束日期</label>
          <input type="date" v-model="form.end_date" class="form-input" />
        </div>
        <div class="config-field">
          <label>初始资金</label>
          <input type="number" v-model.number="form.initial_capital" class="form-input" />
        </div>
        <button class="btn-primary" @click="onRun" :disabled="running">
          {{ running ? '回测中...' : '开始回测' }}
        </button>
      </div>
    </div>

    <!-- Result -->
    <template v-if="result && result.status === 'completed'">
      <!-- Summary cards -->
      <div class="summary-grid">
        <div class="card summary-card" v-for="item in summaryItems" :key="item.label">
          <div class="summary-label">{{ item.label }}</div>
          <div class="summary-value" :class="item.colorClass">{{ item.value }}</div>
        </div>
      </div>

      <!-- Equity curve -->
      <div class="card chart-card">
        <h2 class="section-title">收益曲线</h2>
        <div ref="chartRef" class="equity-chart" />
      </div>

      <!-- Trade table -->
      <div class="card trades-card">
        <h2 class="section-title">交易明细 ({{ result.trades?.length || 0 }} 笔)</h2>
        <div class="trades-table-wrapper">
          <table class="trades-table">
            <thead>
              <tr>
                <th>股票</th><th>买入日</th><th>买入价</th>
                <th>卖出日</th><th>卖出价</th><th>持有</th>
                <th>盈亏</th><th>原因</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(t, i) in result.trades" :key="i">
                <td>{{ t.name }} <span class="trade-code">{{ t.code }}</span></td>
                <td>{{ t.buy_date }}</td>
                <td>{{ t.buy_price.toFixed(2) }}</td>
                <td>{{ t.sell_date }}</td>
                <td>{{ t.sell_price.toFixed(2) }}</td>
                <td>{{ t.hold_days }}天</td>
                <td :class="t.pnl >= 0 ? 'up' : 'down'">
                  {{ t.pnl >= 0 ? '+' : '' }}{{ t.pnl.toFixed(0) }}
                  ({{ t.pnl_pct >= 0 ? '+' : '' }}{{ t.pnl_pct.toFixed(1) }}%)
                </td>
                <td>{{ reasonLabels[t.sell_reason] || t.sell_reason }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>

    <div v-else-if="result && result.status === 'failed'" class="card error-card">
      <p>回测失败: {{ result.error_message }}</p>
    </div>

    <!-- History -->
    <div class="card history-card" v-if="history.length > 0">
      <h2 class="section-title">历史回测</h2>
      <div class="history-list">
        <div v-for="h in history" :key="h.id" class="history-item" @click="loadResult(h.id)">
          <span class="hist-name">{{ h.strategy_name }}</span>
          <span class="hist-range">{{ h.start_date }} ~ {{ h.end_date }}</span>
          <span v-if="h.summary" class="hist-return" :class="h.summary.total_return >= 0 ? 'up' : 'down'">
            {{ (h.summary.total_return * 100).toFixed(1) }}%
          </span>
          <span v-else class="hist-status">{{ h.status }}</span>
          <button class="btn-sm btn-danger" @click.stop="onDeleteHistory(h.id)">删除</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { listStrategies, type StrategyTemplate } from '@/api/strategy'
import { runBacktest, getBacktest, listBacktests, deleteBacktest, type BacktestResult } from '@/api/backtest'
import * as echarts from 'echarts'

const strategies = ref<StrategyTemplate[]>([])
const form = ref({ strategy_id: 0, start_date: '2025-09-01', end_date: '2026-05-26', initial_capital: 50000 })
const running = ref(false)
const result = ref<BacktestResult | null>(null)
const history = ref<BacktestResult[]>([])
const chartRef = ref<HTMLElement | null>(null)
let chart: echarts.ECharts | null = null
let pollTimer: ReturnType<typeof setInterval> | null = null

const reasonLabels: Record<string, string> = {
  stop_loss: '止损', take_profit: '止盈',
  max_hold_days: '到期', trailing_stop: '移动止盈',
}

const summaryItems = computed(() => {
  const s = result.value?.summary
  if (!s) return []
  return [
    { label: '总收益率', value: `${(s.total_return * 100).toFixed(1)}%`, colorClass: s.total_return >= 0 ? 'up' : 'down' },
    { label: '年化收益', value: `${(s.annual_return * 100).toFixed(1)}%`, colorClass: s.annual_return >= 0 ? 'up' : 'down' },
    { label: '最大回撤', value: `${(s.max_drawdown * 100).toFixed(1)}%`, colorClass: 'down' },
    { label: '胜率', value: `${(s.win_rate * 100).toFixed(0)}%`, colorClass: '' },
    { label: '夏普比率', value: `${s.sharpe_ratio.toFixed(2)}`, colorClass: '' },
    { label: '盈亏比', value: `${s.profit_loss_ratio.toFixed(2)}`, colorClass: '' },
    { label: '交易次数', value: `${s.total_trades}`, colorClass: '' },
    { label: '最终资金', value: `¥${s.final_value.toLocaleString()}`, colorClass: s.total_return >= 0 ? 'up' : 'down' },
  ]
})

function renderChart() {
  if (!chartRef.value || !result.value?.daily_values?.length) return
  if (!chart) chart = echarts.init(chartRef.value)
  const dv = result.value.daily_values
  const initVal = result.value.initial_capital
  chart.setOption({
    grid: { top: 30, right: 20, bottom: 30, left: 60 },
    xAxis: { type: 'category', data: dv.map(d => d.date), axisLabel: { color: '#8b95a5', fontSize: 11 } },
    yAxis: { type: 'value', axisLabel: { color: '#8b95a5', fontSize: 11, formatter: (v: number) => `¥${(v/1000).toFixed(0)}k` }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } } },
    tooltip: { trigger: 'axis', formatter: (p: any) => `${p[0].name}<br/>净值: ¥${p[0].value.toLocaleString()}<br/>收益: ${((p[0].value - initVal) / initVal * 100).toFixed(1)}%` },
    series: [{ type: 'line', data: dv.map(d => d.value), smooth: true, symbol: 'none', lineStyle: { color: '#3b82f6', width: 2 }, areaStyle: { color: new echarts.graphic.LinearGradient(0,0,0,1,[{offset:0,color:'rgba(59,130,246,0.3)'},{offset:1,color:'rgba(59,130,246,0.02)'}]) } }],
  })
}

async function onRun() {
  if (!form.value.strategy_id) return
  running.value = true
  result.value = null
  try {
    const { data } = await runBacktest(form.value)
    result.value = data
    pollTimer = setInterval(async () => {
      const { data: latest } = await getBacktest(data.id)
      result.value = latest
      if (latest.status !== 'running') {
        if (pollTimer) clearInterval(pollTimer)
        pollTimer = null
        running.value = false
        await loadHistory()
        await nextTick()
        renderChart()
      }
    }, 2000)
  } catch { running.value = false }
}

async function loadResult(id: number) {
  const { data } = await getBacktest(id)
  result.value = data
  await nextTick()
  renderChart()
}

async function loadHistory() {
  try { const { data } = await listBacktests(); history.value = data } catch {}
}

async function onDeleteHistory(id: number) {
  await deleteBacktest(id)
  await loadHistory()
  if (result.value?.id === id) result.value = null
}

onMounted(async () => {
  const { data } = await listStrategies()
  strategies.value = data
  if (data.length) form.value.strategy_id = data[0].id
  await loadHistory()
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
  if (chart) { chart.dispose(); chart = null }
})
</script>

<style scoped>
.backtest-page { padding: 0; }
.page-title { font-size: 22px; font-weight: 700; margin-bottom: 20px; }

.config-panel { padding: 16px 20px; background: var(--color-surface-elevated, #1a1f2e); border-radius: 12px; margin-bottom: 20px; }
.config-row { display: flex; gap: 16px; align-items: flex-end; flex-wrap: wrap; }
.config-field { display: flex; flex-direction: column; gap: 4px; }
.config-field label { font-size: 12px; color: #8b95a5; }
.form-select, .form-input { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 6px; padding: 8px 12px; color: #e0e6ed; font-size: 14px; }
.btn-primary { background: #3b82f6; color: #fff; border: none; border-radius: 8px; padding: 8px 20px; font-size: 14px; font-weight: 500; cursor: pointer; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

.summary-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; }
.summary-card { padding: 14px 16px; background: var(--color-surface-elevated, #1a1f2e); border-radius: 10px; }
.summary-label { font-size: 12px; color: #8b95a5; margin-bottom: 4px; }
.summary-value { font-size: 20px; font-weight: 700; }

.chart-card { padding: 16px 20px; background: var(--color-surface-elevated, #1a1f2e); border-radius: 12px; margin-bottom: 20px; }
.section-title { font-size: 16px; font-weight: 600; margin-bottom: 12px; }
.equity-chart { width: 100%; height: 300px; }

.trades-card { padding: 16px 20px; background: var(--color-surface-elevated, #1a1f2e); border-radius: 12px; margin-bottom: 20px; }
.trades-table-wrapper { overflow-x: auto; }
.trades-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.trades-table th { text-align: left; padding: 8px 10px; color: #8b95a5; border-bottom: 1px solid rgba(255,255,255,0.08); font-weight: 500; }
.trades-table td { padding: 8px 10px; border-bottom: 1px solid rgba(255,255,255,0.04); }
.trade-code { font-size: 11px; color: #8b95a5; margin-left: 4px; }

.error-card { padding: 20px; background: var(--color-surface-elevated, #1a1f2e); border-radius: 12px; color: #ef4444; margin-bottom: 20px; }

.history-card { padding: 16px 20px; background: var(--color-surface-elevated, #1a1f2e); border-radius: 12px; }
.history-list { display: flex; flex-direction: column; gap: 8px; }
.history-item { display: flex; align-items: center; gap: 12px; padding: 10px 12px; border-radius: 8px; background: rgba(255,255,255,0.03); cursor: pointer; }
.history-item:hover { background: rgba(255,255,255,0.06); }
.hist-name { font-weight: 500; min-width: 80px; }
.hist-range { font-size: 12px; color: #8b95a5; flex: 1; }
.hist-return { font-weight: 600; font-size: 14px; }
.hist-status { font-size: 12px; color: #8b95a5; }

.btn-sm { background: rgba(255,255,255,0.08); border: none; border-radius: 4px; padding: 4px 10px; color: #e0e6ed; font-size: 12px; cursor: pointer; }
.btn-sm:hover { background: rgba(255,255,255,0.12); }
.btn-danger { color: #ef4444; }

.up { color: #ef4444; }
.down { color: #22c55e; }

.card { background: var(--color-surface-elevated, #1a1f2e); border-radius: 12px; }

@media (max-width: 768px) {
  .summary-grid { grid-template-columns: repeat(2, 1fr); }
  .config-row { flex-direction: column; }
}
</style>
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/backtest.ts frontend/src/views/BacktestView.vue
git commit -m "feat: add backtest page with equity curve and trade table"
```

---

### Task 9: Frontend Router + Sidebar

**Files:**
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/components/layout/AppSidebar.vue`

- [ ] **Step 1: Add backtest route**

Read `frontend/src/router/index.ts`. Add this route after the `/realtime` route:

```typescript
{ path: '/backtest', name: 'backtest', component: () => import('@/views/BacktestView.vue') },
```

- [ ] **Step 2: Add sidebar nav entry**

Read `frontend/src/components/layout/AppSidebar.vue`. Add a "策略回测" nav item after "实时监控" and before "学习中心". Match the existing pattern (icon import + nav item structure). Use an appropriate icon from `@element-plus/icons-vue` (e.g., `TrendCharts` or `DataAnalysis`).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/router/index.ts frontend/src/components/layout/AppSidebar.vue
git commit -m "feat: add backtest route and sidebar navigation"
```

---

### Task 10: Integration Test + Build Verification

**Files:**
- No new files — verification only

- [ ] **Step 1: Run full backend test suite**

Run: `cd backend && python -m pytest -v`
Expected: All tests PASS

- [ ] **Step 2: Run frontend build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Verify imports**

Run: `cd backend && python -c "from app.models.strategy import StrategyTemplate, BacktestResult; from app.api.strategy import router; from app.api.backtest import router; from app.services.backtest.engine import BacktestEngine; print('All imports OK')"`

- [ ] **Step 4: Push**

```bash
git push origin master
```
