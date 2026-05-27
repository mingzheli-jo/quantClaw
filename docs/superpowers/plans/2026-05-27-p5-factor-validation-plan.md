# P5: Factor Validation (因子有效性检验) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validate which of the 4 scoring factors (tech, fund, momentum, sentiment) actually predict next-day returns, how stable they are, and whether weights should be adjusted — surfaced in a frontend dashboard with IC trend charts, decay curves, and AI-powered weight suggestions.

**Architecture:** A `services/factor/` module calculates daily Spearman IC between factor scores and forward returns, then aggregates into IC_IR, quintile returns, and decay curves. Results are stored in `FactorIC` (daily) and `FactorReport` (weekly) tables, exposed via API, and displayed in a dedicated frontend page with ECharts.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, SciPy (spearmanr), Vue 3, TypeScript, ECharts

**Prerequisite:** At least 20 trading days of signal data in the database. P4 LLM client is optional (for AI commentary on reports).

---

## File Map

### New Files (Backend)

| File | Responsibility |
|------|---------------|
| `backend/app/services/factor/__init__.py` | Package init |
| `backend/app/services/factor/calculator.py` | Daily IC calculation per factor |
| `backend/app/services/factor/validator.py` | IC_IR, decay, quintile returns, rating |
| `backend/app/services/factor/report.py` | Weight suggestion + AI commentary |
| `backend/app/models/factor.py` | FactorIC + FactorReport models |
| `backend/app/api/factor.py` | Factor API endpoints |
| `backend/tests/test_factor_calculator.py` | Calculator tests |
| `backend/tests/test_factor_validator.py` | Validator tests |

### New Files (Frontend)

| File | Responsibility |
|------|---------------|
| `frontend/src/api/factor.ts` | Factor API client |
| `frontend/src/views/FactorView.vue` | 因子验证 page |

### Modified Files

| File | Changes |
|------|---------|
| `backend/app/models/__init__.py` | Register FactorIC, FactorReport |
| `backend/app/api/__init__.py` | Register factor router |
| `backend/app/scheduler/jobs.py` | Add job_factor_validate |
| `backend/app/scheduler/setup.py` | Schedule weekly job (Sunday 20:00) |
| `frontend/src/router/index.ts` | Add /factor route |
| `frontend/src/components/layout/AppSidebar.vue` | Add nav entry |

---

### Task 1: Factor Models

**Files:**
- Create: `backend/app/models/factor.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Create models**

```python
# backend/app/models/factor.py
from datetime import date, datetime

from sqlalchemy import String, Date, Float, Integer, Text, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FactorIC(Base):
    __tablename__ = "factor_ic"
    __table_args__ = (UniqueConstraint("trade_date", "factor_name", name="uq_factor_ic_date_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, index=True)
    factor_name: Mapped[str] = mapped_column(String(20))
    ic_value: Mapped[float] = mapped_column(Float)
    stock_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class FactorReport(Base):
    __tablename__ = "factor_report"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_date: Mapped[date] = mapped_column(Date, index=True)
    window_days: Mapped[int] = mapped_column(Integer, default=20)
    results: Mapped[str | None] = mapped_column(Text)
    weight_suggestion: Mapped[str | None] = mapped_column(Text)
    ai_commentary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
```

- [ ] **Step 2: Register models**

In `backend/app/models/__init__.py`, add:

```python
from app.models.factor import FactorIC, FactorReport  # noqa: F401
```

Add `"FactorIC"` and `"FactorReport"` to the `__all__` list.

- [ ] **Step 3: Verify**

Run: `cd backend && python -c "from app.models.factor import FactorIC, FactorReport; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/factor.py backend/app/models/__init__.py
git commit -m "feat(p5): add FactorIC and FactorReport models"
```

---

### Task 2: Factor Calculator (Daily IC)

**Files:**
- Create: `backend/app/services/factor/__init__.py`
- Create: `backend/app/services/factor/calculator.py`
- Test: `backend/tests/test_factor_calculator.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_factor_calculator.py
import numpy as np
from app.services.factor.calculator import compute_ic


def test_compute_ic_perfect_positive():
    scores = [1.0, 2.0, 3.0, 4.0, 5.0]
    returns = [0.1, 0.2, 0.3, 0.4, 0.5]
    ic = compute_ic(scores, returns)
    assert abs(ic - 1.0) < 0.01


def test_compute_ic_perfect_negative():
    scores = [5.0, 4.0, 3.0, 2.0, 1.0]
    returns = [0.1, 0.2, 0.3, 0.4, 0.5]
    ic = compute_ic(scores, returns)
    assert abs(ic - (-1.0)) < 0.01


def test_compute_ic_no_correlation():
    scores = [1.0, 2.0, 3.0, 4.0, 5.0]
    returns = [0.3, 0.1, 0.5, 0.2, 0.4]
    ic = compute_ic(scores, returns)
    assert -0.5 < ic < 0.5


def test_compute_ic_too_few_stocks():
    scores = [1.0, 2.0]
    returns = [0.1, 0.2]
    ic = compute_ic(scores, returns)
    assert ic == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_factor_calculator.py -v`
Expected: FAIL

- [ ] **Step 3: Implement calculator**

Create `backend/app/services/factor/__init__.py` (empty).

```python
# backend/app/services/factor/calculator.py
import logging
from datetime import date, timedelta

from scipy.stats import spearmanr
from sqlalchemy.orm import Session

from app.models.factor import FactorIC
from app.models.signal import Signal
from app.models.stock import StockDaily

logger = logging.getLogger(__name__)

FACTOR_NAMES = ["tech", "fund", "momentum", "sentiment", "total"]
SCORE_FIELDS = {
    "tech": "tech_score",
    "fund": "fund_score",
    "momentum": "momentum_score",
    "sentiment": "sentiment_score",
    "total": "score",
}
MIN_STOCKS = 30


def compute_ic(scores: list[float], returns: list[float]) -> float:
    if len(scores) < MIN_STOCKS or len(scores) != len(returns):
        return 0.0
    corr, _ = spearmanr(scores, returns)
    if corr != corr:  # NaN check
        return 0.0
    return float(corr)


def calculate_daily_ic(db: Session, trade_date: date, forward_days: int = 1) -> list[FactorIC]:
    forward_date = trade_date + timedelta(days=forward_days * 2)
    signals = db.query(Signal).filter(Signal.trade_date == trade_date).all()
    if len(signals) < MIN_STOCKS:
        return []

    code_scores: dict[str, dict] = {}
    for s in signals:
        code_scores[s.code] = {
            "tech": s.tech_score,
            "fund": s.fund_score,
            "momentum": s.momentum_score,
            "sentiment": s.sentiment_score,
            "total": s.score,
        }

    next_returns: dict[str, float] = {}
    for code in code_scores:
        next_day = (
            db.query(StockDaily)
            .filter(StockDaily.code == code, StockDaily.trade_date > trade_date, StockDaily.trade_date <= forward_date)
            .order_by(StockDaily.trade_date)
            .first()
        )
        if next_day and next_day.change_pct is not None:
            next_returns[code] = next_day.change_pct

    common_codes = [c for c in code_scores if c in next_returns]
    if len(common_codes) < MIN_STOCKS:
        return []

    results = []
    returns_list = [next_returns[c] for c in common_codes]
    for factor_name in FACTOR_NAMES:
        scores_list = [code_scores[c][factor_name] for c in common_codes]
        ic = compute_ic(scores_list, returns_list)
        results.append(FactorIC(
            trade_date=trade_date,
            factor_name=factor_name,
            ic_value=ic,
            stock_count=len(common_codes),
        ))
    return results


def backfill_ic(db: Session, window_days: int = 20) -> int:
    today = date.today()
    filled = 0
    for i in range(window_days, 0, -1):
        d = today - timedelta(days=i)
        existing = db.query(FactorIC).filter(FactorIC.trade_date == d).first()
        if existing:
            continue
        records = calculate_daily_ic(db, d)
        for r in records:
            db.add(r)
        if records:
            db.commit()
            filled += 1
    return filled
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_factor_calculator.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/factor/ backend/tests/test_factor_calculator.py
git commit -m "feat(p5): add factor IC calculator with Spearman correlation"
```

---

### Task 3: Factor Validator (IC_IR, Decay, Rating)

**Files:**
- Create: `backend/app/services/factor/validator.py`
- Test: `backend/tests/test_factor_validator.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_factor_validator.py
from app.services.factor.validator import validate_factor, rate_factor, suggest_weights


def test_validate_factor():
    ic_values = [0.05, 0.04, 0.06, 0.03, 0.05, 0.04, 0.05, 0.06, 0.04, 0.05,
                 0.03, 0.05, 0.04, 0.06, 0.05, 0.04, 0.03, 0.05, 0.06, 0.04]
    result = validate_factor("tech", ic_values)
    assert result["factor_name"] == "tech"
    assert result["ic_mean"] > 0.03
    assert result["ic_ir"] > 0
    assert 0 < result["positive_rate"] <= 1.0


def test_rate_factor_strong():
    assert rate_factor(ic_mean=0.05, ic_ir=0.8) == "strong"


def test_rate_factor_moderate():
    assert rate_factor(ic_mean=0.025, ic_ir=0.4) == "moderate"


def test_rate_factor_weak():
    assert rate_factor(ic_mean=0.015, ic_ir=0.2) == "weak"


def test_rate_factor_ineffective():
    assert rate_factor(ic_mean=0.005, ic_ir=0.05) == "ineffective"


def test_suggest_weights():
    results = {
        "tech": {"ic_ir": 1.0},
        "fund": {"ic_ir": 0.5},
        "momentum": {"ic_ir": 0.3},
        "sentiment": {"ic_ir": 0.2},
    }
    weights = suggest_weights(results)
    assert abs(sum(weights.values()) - 1.0) < 0.01
    assert weights["tech"] > weights["fund"] > weights["momentum"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_factor_validator.py -v`
Expected: FAIL

- [ ] **Step 3: Implement validator**

```python
# backend/app/services/factor/validator.py
import statistics


def validate_factor(factor_name: str, ic_values: list[float]) -> dict:
    if not ic_values:
        return {
            "factor_name": factor_name,
            "ic_mean": 0, "ic_std": 0, "ic_ir": 0,
            "positive_rate": 0, "rating": "ineffective",
        }
    ic_mean = statistics.mean(ic_values)
    ic_std = statistics.stdev(ic_values) if len(ic_values) > 1 else 0.001
    ic_ir = ic_mean / ic_std if ic_std > 0 else 0
    positive_rate = sum(1 for v in ic_values if v > 0) / len(ic_values)
    rating = rate_factor(ic_mean, ic_ir)
    return {
        "factor_name": factor_name,
        "ic_mean": round(ic_mean, 4),
        "ic_std": round(ic_std, 4),
        "ic_ir": round(ic_ir, 2),
        "positive_rate": round(positive_rate, 2),
        "rating": rating,
    }


def rate_factor(ic_mean: float, ic_ir: float) -> str:
    if ic_ir > 0.5 and ic_mean > 0.03:
        return "strong"
    if ic_ir > 0.3 and ic_mean > 0.02:
        return "moderate"
    if ic_ir > 0.1 and ic_mean > 0.01:
        return "weak"
    return "ineffective"


def suggest_weights(results: dict[str, dict]) -> dict[str, float]:
    scores = {name: max(r["ic_ir"], 0) for name, r in results.items() if name != "total"}
    total = sum(scores.values()) or 1
    return {name: round(s / total, 2) for name, s in scores.items()}
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_factor_validator.py -v`
Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/factor/validator.py backend/tests/test_factor_validator.py
git commit -m "feat(p5): add factor validator with IC_IR, rating, weight suggestion"
```

---

### Task 4: Factor Report Generator

**Files:**
- Create: `backend/app/services/factor/report.py`

- [ ] **Step 1: Implement report generator**

```python
# backend/app/services/factor/report.py
import json
import logging
from datetime import date

from sqlalchemy.orm import Session

from app.models.factor import FactorIC, FactorReport
from app.services.factor.calculator import FACTOR_NAMES, backfill_ic
from app.services.factor.validator import validate_factor, suggest_weights

logger = logging.getLogger(__name__)


def generate_report(db: Session, window_days: int = 20) -> FactorReport | None:
    backfill_ic(db, window_days)

    factor_results = {}
    for factor_name in FACTOR_NAMES:
        ics = (
            db.query(FactorIC)
            .filter(FactorIC.factor_name == factor_name)
            .order_by(FactorIC.trade_date.desc())
            .limit(window_days)
            .all()
        )
        ic_values = [ic.ic_value for ic in ics]
        factor_results[factor_name] = validate_factor(factor_name, ic_values)

    non_total = {k: v for k, v in factor_results.items() if k != "total"}
    weights = suggest_weights(non_total)

    ai_commentary = ""
    try:
        from app.config import settings
        if settings.deepseek_api_key or settings.qwen_api_key:
            from app.services.ai.llm_client import LLMClient
            key = settings.deepseek_api_key or settings.qwen_api_key
            provider = "deepseek" if settings.deepseek_api_key else "qwen"
            client = LLMClient(api_key=key, provider=provider)
            prompt = (
                f"以下是量化因子验证结果，请用简洁中文总结哪些因子有效、哪些需要调整，"
                f"并解释建议的权重变化：\n{json.dumps(factor_results, ensure_ascii=False)}\n"
                f"建议权重：{json.dumps(weights, ensure_ascii=False)}"
            )
            ai_commentary = client.chat([
                {"role": "system", "content": "你是量化分析专家，用简洁中文回答。200字以内。"},
                {"role": "user", "content": prompt},
            ])
    except Exception as e:
        logger.warning(f"AI commentary generation failed: {e}")

    report = FactorReport(
        report_date=date.today(),
        window_days=window_days,
        results=json.dumps(factor_results, ensure_ascii=False),
        weight_suggestion=json.dumps(weights, ensure_ascii=False),
        ai_commentary=ai_commentary or None,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report
```

- [ ] **Step 2: Verify import**

Run: `cd backend && python -c "from app.services.factor.report import generate_report; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/factor/report.py
git commit -m "feat(p5): add factor report generator with AI commentary"
```

---

### Task 5: Factor API Endpoints

**Files:**
- Create: `backend/app/api/factor.py`
- Modify: `backend/app/api/__init__.py`

- [ ] **Step 1: Create API**

```python
# backend/app/api/factor.py
import json
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.factor import FactorIC, FactorReport
from app.models.signal import Signal
from app.models.system import User

router = APIRouter(prefix="/api/factor", tags=["factor"])


@router.get("/latest")
def latest_report(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    report = db.query(FactorReport).order_by(FactorReport.report_date.desc()).first()
    if not report:
        signal_days = db.query(Signal.trade_date).distinct().count()
        return {"report": None, "data_days": signal_days, "min_days": 20}
    return {
        "report": {
            "report_date": str(report.report_date),
            "window_days": report.window_days,
            "results": json.loads(report.results) if report.results else {},
            "weight_suggestion": json.loads(report.weight_suggestion) if report.weight_suggestion else {},
            "ai_commentary": report.ai_commentary,
        },
        "data_days": None,
        "min_days": 20,
    }


@router.get("/ic-history")
def ic_history(
    days: int = Query(60, ge=5, le=120),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    cutoff = date.today() - timedelta(days=days)
    ics = (
        db.query(FactorIC)
        .filter(FactorIC.trade_date >= cutoff)
        .order_by(FactorIC.trade_date)
        .all()
    )
    result: dict[str, list] = {}
    for ic in ics:
        if ic.factor_name not in result:
            result[ic.factor_name] = []
        result[ic.factor_name].append({
            "date": str(ic.trade_date),
            "ic": ic.ic_value,
            "count": ic.stock_count,
        })
    return result


@router.post("/run")
def run_validation(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    today = date.today()
    existing = db.query(FactorReport).filter(FactorReport.report_date == today).first()
    if existing:
        return {"message": "今日已生成报告", "report_date": str(today)}
    from app.services.factor.report import generate_report
    report = generate_report(db)
    if not report:
        raise HTTPException(status_code=400, detail="数据不足，无法生成因子报告")
    return {"message": "报告已生成", "report_date": str(report.report_date)}
```

- [ ] **Step 2: Register router**

In `backend/app/api/__init__.py`, add:

```python
from app.api.factor import router as factor_router
api_router.include_router(factor_router)
```

- [ ] **Step 3: Verify**

Run: `cd backend && python -c "from app.api.factor import router; print([r.path for r in router.routes])"`
Expected: paths including `/api/factor/latest`, `/api/factor/ic-history`, `/api/factor/run`

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/factor.py backend/app/api/__init__.py
git commit -m "feat(p5): add factor validation API endpoints"
```

---

### Task 6: Scheduler Job (Weekly)

**Files:**
- Modify: `backend/app/scheduler/jobs.py`
- Modify: `backend/app/scheduler/setup.py`

- [ ] **Step 1: Add job to jobs.py**

Add at the end of `backend/app/scheduler/jobs.py`:

```python
def job_factor_validate():
    started = datetime.now()
    db = SessionLocal()
    try:
        from app.services.factor.report import generate_report
        report = generate_report(db)
        msg = f"Report generated: window={report.window_days}d" if report else "Insufficient data"
        _log_job(db, "factor_validate", "success", msg, started_at=started)
    except Exception as e:
        logger.error(f"Factor validation failed: {e}", exc_info=True)
        _log_job(db, "factor_validate", "failed", str(e), started_at=started, error_message=str(e))
    finally:
        db.close()
```

- [ ] **Step 2: Register in setup.py**

In `backend/app/scheduler/setup.py`, add import:

```python
from app.scheduler.jobs import (
    ...
    job_factor_validate,
)
```

Add job in `start_scheduler()`:

```python
    scheduler.add_job(
        job_factor_validate, CronTrigger(day_of_week="sun", hour=20, minute=0),
        id="factor_validate", replace_existing=True,
    )
```

- [ ] **Step 3: Verify**

Run: `cd backend && python -c "from app.scheduler.setup import start_scheduler; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/app/scheduler/jobs.py backend/app/scheduler/setup.py
git commit -m "feat(p5): add weekly factor validation scheduler job"
```

---

### Task 7: Frontend — Factor Validation Page

**Files:**
- Create: `frontend/src/api/factor.ts`
- Create: `frontend/src/views/FactorView.vue`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/components/layout/AppSidebar.vue`

- [ ] **Step 1: Create API client**

```typescript
// frontend/src/api/factor.ts
import client from './client'

export interface FactorResult {
  factor_name: string
  ic_mean: number
  ic_std: number
  ic_ir: number
  positive_rate: number
  rating: string
}

export interface FactorReportData {
  report_date: string
  window_days: number
  results: Record<string, FactorResult>
  weight_suggestion: Record<string, number>
  ai_commentary: string | null
}

export interface LatestReportResponse {
  report: FactorReportData | null
  data_days: number | null
  min_days: number
}

export interface ICPoint {
  date: string
  ic: number
  count: number
}

export function fetchLatestReport() {
  return client.get<LatestReportResponse>('/factor/latest')
}

export function fetchICHistory(days = 60) {
  return client.get<Record<string, ICPoint[]>>('/factor/ic-history', { params: { days } })
}

export function runValidation() {
  return client.post('/factor/run')
}
```

- [ ] **Step 2: Create FactorView.vue**

```vue
<!-- frontend/src/views/FactorView.vue -->
<template>
  <div class="factor-page">
    <div class="page-header">
      <h2>因子验证</h2>
      <el-button size="small" @click="handleRun" :loading="running">手动运行</el-button>
    </div>

    <div v-if="!report" class="empty-state">
      <p>数据积累中</p>
      <p class="hint">需要至少 20 个交易日的信号数据，当前: {{ dataDays ?? 0 }} 天</p>
      <el-progress :percentage="Math.min(100, ((dataDays ?? 0) / 20) * 100)" :stroke-width="8" style="max-width: 300px; margin: 16px auto" />
    </div>

    <template v-else>
      <div class="summary-cards">
        <div v-for="name in factorOrder" :key="name" class="factor-card">
          <div class="factor-name">{{ factorLabels[name] }}</div>
          <div class="factor-ir">IC_IR: {{ report.results[name]?.ic_ir ?? '-' }}</div>
          <el-tag :type="ratingType(report.results[name]?.rating)" size="small">{{ report.results[name]?.rating }}</el-tag>
          <div class="weight-row">
            <span>当前 {{ currentWeights[name] ?? '-' }}%</span>
            <span>→</span>
            <span class="suggested">{{ ((report.weight_suggestion[name] ?? 0) * 100).toFixed(0) }}%</span>
          </div>
        </div>
      </div>

      <div class="card" style="margin-top: 24px">
        <div class="card-title">IC 趋势</div>
        <div ref="icChartRef" style="height: 350px" />
      </div>

      <div class="card" style="margin-top: 20px">
        <div class="card-title">详细数据</div>
        <el-table :data="tableData" stripe>
          <el-table-column prop="label" label="因子" width="100" />
          <el-table-column prop="ic_mean" label="IC均值" width="100" />
          <el-table-column prop="ic_std" label="IC标准差" width="100" />
          <el-table-column prop="ic_ir" label="IC_IR" width="80" />
          <el-table-column prop="positive_rate" label="正比例" width="80">
            <template #default="{ row }">{{ (row.positive_rate * 100).toFixed(0) }}%</template>
          </el-table-column>
          <el-table-column prop="rating" label="评级" width="100">
            <template #default="{ row }">
              <el-tag :type="ratingType(row.rating)" size="small">{{ row.rating }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div class="card" v-if="report.ai_commentary" style="margin-top: 20px">
        <div class="card-title">🤖 AI 解读</div>
        <p class="ai-text">{{ report.ai_commentary }}</p>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import { fetchLatestReport, fetchICHistory, runValidation, type FactorReportData } from '@/api/factor'

const report = ref<FactorReportData | null>(null)
const dataDays = ref<number | null>(null)
const running = ref(false)
const icChartRef = ref<HTMLElement>()
let icChart: echarts.ECharts | null = null

const factorOrder = ['tech', 'fund', 'momentum', 'sentiment']
const factorLabels: Record<string, string> = { tech: '技术面', fund: '资金面', momentum: '动量', sentiment: '情绪面' }
const currentWeights: Record<string, number> = { tech: 40, fund: 30, momentum: 20, sentiment: 10 }
const factorColors: Record<string, string> = { tech: '#4ecdc4', fund: '#ffa726', momentum: '#7c4dff', sentiment: '#ef5350', total: '#888' }

const tableData = ref<{ label: string; ic_mean: number; ic_std: number; ic_ir: number; positive_rate: number; rating: string }[]>([])

function ratingType(rating: string | undefined): string {
  if (rating === 'strong') return 'success'
  if (rating === 'moderate') return 'warning'
  if (rating === 'weak') return 'info'
  return 'danger'
}

async function handleRun() {
  running.value = true
  try {
    await runValidation()
    await loadData()
  } catch {}
  running.value = false
}

async function loadData() {
  const { data } = await fetchLatestReport()
  report.value = data.report
  dataDays.value = data.data_days
  if (data.report) {
    tableData.value = factorOrder.map(name => ({
      label: factorLabels[name],
      ...data.report!.results[name],
    }))
    await nextTick()
    await renderICChart()
  }
}

async function renderICChart() {
  if (!icChartRef.value) return
  const { data: history } = await fetchICHistory(60)
  if (!icChart) icChart = echarts.init(icChartRef.value)
  const allDates = new Set<string>()
  for (const points of Object.values(history)) {
    for (const p of points) allDates.add(p.date)
  }
  const dates = Array.from(allDates).sort()
  const series = [...factorOrder, 'total'].map(name => ({
    name: factorLabels[name] || '总分',
    type: 'line' as const,
    data: dates.map(d => {
      const point = history[name]?.find(p => p.date === d)
      return point ? point.ic : null
    }),
    smooth: true,
    lineStyle: { color: factorColors[name] || '#888' },
    itemStyle: { color: factorColors[name] || '#888' },
  }))
  icChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: series.map(s => s.name), bottom: 0 },
    xAxis: { type: 'category', data: dates },
    yAxis: { type: 'value', name: 'IC' },
    series,
    visualMap: { show: false },
  }, true)
}

onMounted(loadData)
</script>

<style scoped>
.page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px; }
.page-header h2 { font-size: 20px; font-weight: 700; color: var(--color-text); }
.empty-state { text-align: center; padding: 60px 0; color: var(--color-text-secondary); }
.hint { font-size: 13px; margin-top: 8px; }
.summary-cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
.factor-card {
  background: var(--color-surface); border: 1px solid var(--color-border);
  border-radius: 12px; padding: 16px; text-align: center;
}
.factor-name { font-size: 14px; font-weight: 600; color: var(--color-text); margin-bottom: 8px; }
.factor-ir { font-size: 20px; font-weight: 700; color: var(--color-text); margin-bottom: 8px; font-variant-numeric: tabular-nums; }
.weight-row { display: flex; justify-content: center; gap: 8px; font-size: 13px; color: var(--color-text-secondary); margin-top: 8px; }
.suggested { color: var(--color-accent); font-weight: 600; }
.card { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 12px; padding: 20px; }
.card-title { font-size: 14px; font-weight: 700; color: var(--color-text); margin-bottom: 16px; }
.ai-text { font-size: 14px; color: var(--color-text); line-height: 1.6; }
</style>
```

- [ ] **Step 3: Add route**

In `frontend/src/router/index.ts`, add before `/learn`:

```typescript
{ path: '/factor', name: 'factor', component: () => import('@/views/FactorView.vue') },
```

- [ ] **Step 4: Add sidebar entry**

In `frontend/src/components/layout/AppSidebar.vue`, add `DataAnalysis` to icon imports:

```typescript
import { ..., DataAnalysis } from '@element-plus/icons-vue'
```

Add to navItems after "策略回测":

```typescript
{ path: '/factor', label: '因子验证', icon: DataAnalysis },
```

- [ ] **Step 5: Build frontend**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/factor.ts frontend/src/views/FactorView.vue frontend/src/router/index.ts frontend/src/components/layout/AppSidebar.vue
git commit -m "feat(p5): add factor validation frontend page"
```

---

### Task 8: Deploy

**Operational — no code.**

- [ ] **Step 1: Install scipy in Docker**

Add `scipy` to `backend/requirements.txt` (or wherever dependencies are listed).

- [ ] **Step 2: Push and deploy**

```bash
git push
# On server:
cd /opt/quantClaw && git pull && sudo bash start.sh
```

- [ ] **Step 3: Verify factor page shows "数据积累中"**

Visit `https://quant.azhefuye.online/factor` — should show the progress bar.

---

## Summary

| Task | What it delivers |
|------|-----------------|
| 1 | FactorIC + FactorReport database models |
| 2 | Daily IC calculator (Spearman correlation) |
| 3 | Validator (IC_IR, rating, weight suggestion) |
| 4 | Report generator with optional AI commentary |
| 5 | Factor API (latest, ic-history, run) |
| 6 | Weekly scheduler job (Sunday 20:00) |
| 7 | Factor validation frontend page |
| 8 | Deploy + verify |

Total: **8 tasks**, runs independently of P4 (AI commentary is optional fallback).
