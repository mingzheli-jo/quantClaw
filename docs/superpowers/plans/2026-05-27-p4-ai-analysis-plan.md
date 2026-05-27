# P4: AI 智能分析 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add LLM-powered stock analysis that generates plain-language reports explaining why stocks are recommended, their risks, and actionable suggestions — delivered via a dedicated AI page, stock detail integration, and Feishu notifications.

**Architecture:** A `services/ai/` module provides a unified LLM client (DeepSeek default), a context builder that collects stock data, and an analyzer that orchestrates report generation. Results are persisted in an `AIAnalysis` table and surfaced via API, frontend page, and Feishu cards.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, DeepSeek API (OpenAI-compatible), Vue 3, TypeScript, Element Plus

---

## File Map

### New Files (Backend)

| File | Responsibility |
|------|---------------|
| `backend/app/services/ai/__init__.py` | Package init |
| `backend/app/services/ai/llm_client.py` | Unified LLM interface with DeepSeek provider |
| `backend/app/services/ai/prompts.py` | System + user prompt templates |
| `backend/app/services/ai/analyzer.py` | Context builder + analysis orchestrator |
| `backend/app/models/ai.py` | AIAnalysis SQLAlchemy model |
| `backend/app/api/ai.py` | AI API endpoints |
| `backend/tests/test_llm_client.py` | LLM client tests |
| `backend/tests/test_analyzer.py` | Analyzer tests |

### New Files (Frontend)

| File | Responsibility |
|------|---------------|
| `frontend/src/api/ai.ts` | AI API client |
| `frontend/src/views/AIInsightView.vue` | AI 洞察 page |

### Modified Files

| File | Changes |
|------|---------|
| `backend/app/config.py` | Add `deepseek_api_key` setting |
| `backend/app/models/__init__.py` | Register AIAnalysis |
| `backend/app/api/__init__.py` | Register AI router |
| `backend/app/scheduler/jobs.py` | Add `job_ai_analysis` |
| `backend/app/scheduler/setup.py` | Schedule AI job at 15:40 |
| `backend/app/services/notify/messages.py` | Append AI summary to Feishu card |
| `frontend/src/views/StockDetailView.vue` | Add AI analysis card + generate button |
| `frontend/src/router/index.ts` | Add `/ai` route |
| `frontend/src/components/layout/AppSidebar.vue` | Add "AI 洞察" nav entry |

---

### Task 1: LLM Client

**Files:**
- Create: `backend/app/services/ai/__init__.py`
- Create: `backend/app/services/ai/llm_client.py`
- Modify: `backend/app/config.py`
- Test: `backend/tests/test_llm_client.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_llm_client.py
from unittest.mock import patch, MagicMock
from app.services.ai.llm_client import LLMClient


def test_chat_returns_string():
    client = LLMClient(api_key="test-key", provider="deepseek")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "test response"}}]
    }
    with patch("httpx.post", return_value=mock_resp):
        result = client.chat([{"role": "user", "content": "hello"}])
    assert result == "test response"


def test_chat_retries_on_failure():
    client = LLMClient(api_key="test-key", provider="deepseek")
    mock_fail = MagicMock(side_effect=Exception("timeout"))
    mock_ok = MagicMock()
    mock_ok.status_code = 200
    mock_ok.json.return_value = {
        "choices": [{"message": {"content": "ok"}}]
    }
    with patch("httpx.post", side_effect=[Exception("timeout"), mock_ok]):
        result = client.chat([{"role": "user", "content": "hello"}])
    assert result == "ok"


def test_chat_returns_empty_after_all_retries():
    client = LLMClient(api_key="test-key", provider="deepseek")
    with patch("httpx.post", side_effect=Exception("timeout")):
        result = client.chat([{"role": "user", "content": "hello"}])
    assert result == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_llm_client.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Add deepseek_api_key to config**

In `backend/app/config.py`, add to the `Settings` class:

```python
    deepseek_api_key: str = ""
    qwen_api_key: str = ""
    llm_provider: str = "deepseek"
```

- [ ] **Step 4: Implement LLM client**

Create `backend/app/services/ai/__init__.py` (empty file).

Create `backend/app/services/ai/llm_client.py`:

```python
import logging
import time

import httpx

logger = logging.getLogger(__name__)

_PROVIDER_CONFIG = {
    "deepseek": {
        "url": "https://api.deepseek.com/chat/completions",
        "model": "deepseek-chat",
    },
    "qwen": {
        "url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "model": "qwen-plus",
    },
}

_MAX_RETRIES = 2
_RETRY_DELAY = 3
_TIMEOUT = 30


class LLMClient:
    def __init__(self, api_key: str, provider: str = "deepseek"):
        self._api_key = api_key
        self._provider = provider
        cfg = _PROVIDER_CONFIG.get(provider, _PROVIDER_CONFIG["deepseek"])
        self._url = cfg["url"]
        self._model = cfg["model"]

    def chat(self, messages: list[dict], temperature: float = 0.3) -> str:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 1024,
        }
        for attempt in range(_MAX_RETRIES + 1):
            try:
                resp = httpx.post(self._url, json=payload, headers=headers, timeout=_TIMEOUT)
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            except Exception as e:
                logger.warning(f"LLM call attempt {attempt + 1} failed: {e}")
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_DELAY)
        logger.error("LLM call failed after all retries")
        return ""
```

- [ ] **Step 5: Run tests**

Run: `cd backend && python -m pytest tests/test_llm_client.py -v`
Expected: 3 PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/ai/ backend/app/config.py backend/tests/test_llm_client.py
git commit -m "feat(p4): add LLM client with DeepSeek/Qwen support"
```

---

### Task 2: Prompt Templates

**Files:**
- Create: `backend/app/services/ai/prompts.py`

- [ ] **Step 1: Create prompts module**

```python
# backend/app/services/ai/prompts.py
import json

SYSTEM_PROMPT = """你是 QuantClaw 量化信号系统的 AI 分析师。用户是量化小白，需要你用通俗易懂的语言解释股票信号。

分析要求：
1. 推荐理由：用人话解释技术指标的含义，说明为什么系统推荐这只股
2. 风险提示：指出 2-3 个潜在风险（技术面见顶信号、板块轮动、大盘环境等）
3. 操作建议：给出明确建议（积极买入/等回调/观望/建议减仓），并说明理由
4. 市场环境：一句话总结今天大盘对这只股票的影响

严格按以下 JSON 格式输出，不要输出其他内容：
{"summary": "推荐理由", "risk": "风险提示", "suggestion": "操作建议", "market_comment": "市场环境"}

语言风格：简洁直白，像一个经验丰富的朋友在微信上给你建议。每段不超过 3 句话。"""


def build_user_prompt(context: dict) -> str:
    return f"请分析以下股票数据并给出建议：\n\n{json.dumps(context, ensure_ascii=False, indent=2)}"


def build_messages(context: dict) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(context)},
    ]
```

- [ ] **Step 2: Verify import**

Run: `cd backend && python -c "from app.services.ai.prompts import build_messages; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/ai/prompts.py
git commit -m "feat(p4): add AI prompt templates"
```

---

### Task 3: AIAnalysis Model

**Files:**
- Create: `backend/app/models/ai.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Create model**

```python
# backend/app/models/ai.py
from datetime import date, datetime

from sqlalchemy import String, Date, Text, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AIAnalysis(Base):
    __tablename__ = "ai_analysis"
    __table_args__ = (UniqueConstraint("code", "trade_date", name="uq_ai_analysis_code_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(10), index=True)
    trade_date: Mapped[date] = mapped_column(Date, index=True)
    summary: Mapped[str | None] = mapped_column(Text)
    risk: Mapped[str | None] = mapped_column(Text)
    suggestion: Mapped[str | None] = mapped_column(Text)
    market_comment: Mapped[str | None] = mapped_column(Text)
    llm_provider: Mapped[str] = mapped_column(String(20), default="deepseek")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
```

- [ ] **Step 2: Register in models/__init__.py**

Add to `backend/app/models/__init__.py`:

```python
from app.models.ai import AIAnalysis  # noqa: F401
```

And add `"AIAnalysis"` to the `__all__` list.

- [ ] **Step 3: Verify**

Run: `cd backend && python -c "from app.models.ai import AIAnalysis; print([c.name for c in AIAnalysis.__table__.columns])"`
Expected: list of column names

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/ai.py backend/app/models/__init__.py
git commit -m "feat(p4): add AIAnalysis model"
```

---

### Task 4: Analyzer (Context Builder + Orchestrator)

**Files:**
- Create: `backend/app/services/ai/analyzer.py`
- Test: `backend/tests/test_analyzer.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_analyzer.py
import json
from datetime import date
from unittest.mock import patch, MagicMock

from app.services.ai.analyzer import build_stock_context, analyze_stock


def test_build_stock_context():
    db = MagicMock()
    signal = MagicMock()
    signal.code = "000001"
    signal.stock_name = "平安银行"
    signal.score = 72
    signal.tech_score = 28
    signal.fund_score = 22
    signal.momentum_score = 14
    signal.sentiment_score = 8
    signal.reason = "MA5上穿MA20"
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = signal
    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
    db.query.return_value.filter.return_value.first.return_value = None

    ctx = build_stock_context(db, "000001")
    assert ctx["code"] == "000001"
    assert ctx["scores"]["total"] == 72
    assert ctx["reason"] == "MA5上穿MA20"


def test_analyze_stock_parses_json():
    db = MagicMock()
    mock_ctx = {"code": "000001", "name": "Test", "scores": {}, "reason": ""}
    llm_response = json.dumps({
        "summary": "test summary",
        "risk": "test risk",
        "suggestion": "test suggestion",
        "market_comment": "test comment",
    })
    with patch("app.services.ai.analyzer.build_stock_context", return_value=mock_ctx):
        with patch("app.services.ai.analyzer._get_llm_client") as mock_llm:
            mock_llm.return_value.chat.return_value = llm_response
            result = analyze_stock(db, "000001")
    assert result["summary"] == "test summary"
    assert result["risk"] == "test risk"


def test_analyze_stock_handles_malformed_response():
    db = MagicMock()
    mock_ctx = {"code": "000001", "name": "Test", "scores": {}, "reason": ""}
    with patch("app.services.ai.analyzer.build_stock_context", return_value=mock_ctx):
        with patch("app.services.ai.analyzer._get_llm_client") as mock_llm:
            mock_llm.return_value.chat.return_value = "not json, just plain text analysis"
            result = analyze_stock(db, "000001")
    assert result["summary"] == "not json, just plain text analysis"
    assert result["risk"] == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_analyzer.py -v`
Expected: FAIL

- [ ] **Step 3: Implement analyzer**

```python
# backend/app/services/ai/analyzer.py
import json
import logging
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.models.market import MarketSentiment, NorthFlow, SectorDaily
from app.models.signal import Signal
from app.models.stock import StockBasic, StockDaily
from app.models.position import Position
from app.services.ai.llm_client import LLMClient
from app.services.ai.prompts import build_messages

logger = logging.getLogger(__name__)


def _get_llm_client() -> LLMClient:
    provider = settings.llm_provider
    key_map = {"deepseek": settings.deepseek_api_key, "qwen": settings.qwen_api_key}
    api_key = key_map.get(provider, settings.deepseek_api_key)
    return LLMClient(api_key=api_key, provider=provider)


def build_stock_context(db: Session, code: str) -> dict:
    today = date.today()
    stock = db.query(StockBasic).filter(StockBasic.code == code).first()
    signal = db.query(Signal).filter(Signal.code == code).order_by(Signal.trade_date.desc()).first()
    klines = (
        db.query(StockDaily)
        .filter(StockDaily.code == code)
        .order_by(StockDaily.trade_date.desc())
        .limit(5)
        .all()
    )
    klines.reverse()
    sentiment = db.query(MarketSentiment).filter(MarketSentiment.trade_date == today).first()
    north = db.query(NorthFlow).order_by(NorthFlow.trade_date.desc()).first()
    industry = stock.industry if stock else ""
    sector = db.query(SectorDaily).filter(
        SectorDaily.sector == industry, SectorDaily.trade_date == today
    ).first()
    position = db.query(Position).filter(
        Position.code == code, Position.status == "open"
    ).first()

    return {
        "code": code,
        "name": stock.name if stock else code,
        "industry": industry,
        "scores": {
            "total": signal.score if signal else 0,
            "tech": signal.tech_score if signal else 0,
            "fund": signal.fund_score if signal else 0,
            "momentum": signal.momentum_score if signal else 0,
            "sentiment": signal.sentiment_score if signal else 0,
        },
        "reason": signal.reason if signal else "",
        "kline_5d": [
            {
                "date": str(k.trade_date),
                "close": k.close,
                "change_pct": k.change_pct or 0,
                "volume": k.volume,
            }
            for k in klines
        ],
        "market": {
            "up_count": sentiment.up_count if sentiment else 0,
            "down_count": sentiment.down_count if sentiment else 0,
            "limit_up": sentiment.limit_up if sentiment else 0,
            "limit_down": sentiment.limit_down if sentiment else 0,
            "north_net": north.net_amount if north else 0,
        },
        "sector_change_pct": sector.change_pct if sector else 0,
        "position": {
            "buy_price": position.buy_price,
            "hold_days": (today - position.buy_date).days,
            "pnl_pct": round(
                (position.current_price - position.buy_price) / position.buy_price * 100, 2
            ) if position.current_price else 0,
        } if position else None,
    }


def analyze_stock(db: Session, code: str) -> dict:
    context = build_stock_context(db, code)
    client = _get_llm_client()
    messages = build_messages(context)
    raw = client.chat(messages)
    if not raw:
        return {"summary": "AI 分析暂时不可用", "risk": "", "suggestion": "", "market_comment": "", "raw": ""}
    try:
        parsed = json.loads(raw)
        return {
            "summary": parsed.get("summary", ""),
            "risk": parsed.get("risk", ""),
            "suggestion": parsed.get("suggestion", ""),
            "market_comment": parsed.get("market_comment", ""),
            "raw": raw,
        }
    except json.JSONDecodeError:
        return {"summary": raw, "risk": "", "suggestion": "", "market_comment": "", "raw": raw}
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_analyzer.py -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai/analyzer.py backend/tests/test_analyzer.py
git commit -m "feat(p4): add AI analyzer with context builder"
```

---

### Task 5: AI API Endpoints

**Files:**
- Create: `backend/app/api/ai.py`
- Modify: `backend/app/api/__init__.py`

- [ ] **Step 1: Create AI API**

```python
# backend/app/api/ai.py
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.config import settings
from app.models.ai import AIAnalysis
from app.models.signal import Signal
from app.models.system import User
from app.services.ai.analyzer import analyze_stock

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.get("/daily")
def daily_analyses(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    today = date.today()
    analyses = (
        db.query(AIAnalysis)
        .filter(AIAnalysis.trade_date == today)
        .all()
    )
    result = []
    for a in analyses:
        signal = db.query(Signal).filter(
            Signal.code == a.code, Signal.trade_date == today
        ).first()
        result.append({
            "code": a.code,
            "stock_name": signal.stock_name if signal else a.code,
            "score": signal.score if signal else 0,
            "summary": a.summary,
            "risk": a.risk,
            "suggestion": a.suggestion,
            "market_comment": a.market_comment,
            "llm_provider": a.llm_provider,
            "created_at": str(a.created_at),
        })
    return result


@router.get("/{code}")
def get_analysis(
    code: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    analysis = (
        db.query(AIAnalysis)
        .filter(AIAnalysis.code == code)
        .order_by(AIAnalysis.trade_date.desc())
        .first()
    )
    if not analysis:
        return {"code": code, "summary": None}
    return {
        "code": analysis.code,
        "trade_date": str(analysis.trade_date),
        "summary": analysis.summary,
        "risk": analysis.risk,
        "suggestion": analysis.suggestion,
        "market_comment": analysis.market_comment,
        "llm_provider": analysis.llm_provider,
        "created_at": str(analysis.created_at),
    }


@router.post("/generate/{code}")
def generate_analysis(
    code: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not settings.deepseek_api_key and not settings.qwen_api_key:
        raise HTTPException(status_code=503, detail="未配置 AI 服务，请在环境变量中设置 DEEPSEEK_API_KEY")

    today = date.today()
    existing = db.query(AIAnalysis).filter(
        AIAnalysis.code == code, AIAnalysis.trade_date == today
    ).first()
    if existing:
        return {
            "code": existing.code,
            "trade_date": str(existing.trade_date),
            "summary": existing.summary,
            "risk": existing.risk,
            "suggestion": existing.suggestion,
            "market_comment": existing.market_comment,
        }

    today_count = db.query(AIAnalysis).filter(AIAnalysis.trade_date == today).count()
    if today_count >= 20:
        raise HTTPException(status_code=429, detail="今日 AI 分析次数已达上限 (20次)")

    result = analyze_stock(db, code)
    analysis = AIAnalysis(
        code=code,
        trade_date=today,
        summary=result["summary"],
        risk=result["risk"],
        suggestion=result["suggestion"],
        market_comment=result["market_comment"],
        llm_provider=settings.llm_provider,
    )
    db.add(analysis)
    db.commit()
    return {
        "code": code,
        "trade_date": str(today),
        "summary": result["summary"],
        "risk": result["risk"],
        "suggestion": result["suggestion"],
        "market_comment": result["market_comment"],
    }
```

- [ ] **Step 2: Register router**

In `backend/app/api/__init__.py`, add:

```python
from app.api.ai import router as ai_router
api_router.include_router(ai_router)
```

- [ ] **Step 3: Verify**

Run: `cd backend && python -c "from app.api.ai import router; print([r.path for r in router.routes])"`
Expected: paths including `/api/ai/daily`, `/api/ai/{code}`, `/api/ai/generate/{code}`

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/ai.py backend/app/api/__init__.py
git commit -m "feat(p4): add AI analysis API endpoints"
```

---

### Task 6: Scheduler Job for Daily AI Analysis

**Files:**
- Modify: `backend/app/scheduler/jobs.py`
- Modify: `backend/app/scheduler/setup.py`

- [ ] **Step 1: Add job_ai_analysis to jobs.py**

Add at the end of `backend/app/scheduler/jobs.py`:

```python
def job_ai_analysis():
    if not is_trading_day():
        return
    if not settings.deepseek_api_key and not settings.qwen_api_key:
        logger.info("AI analysis skipped: no LLM API key configured")
        return
    started = datetime.now()
    db = SessionLocal()
    try:
        from app.models.ai import AIAnalysis
        from app.models.watchlist import Watchlist
        from app.services.ai.analyzer import analyze_stock

        today = date.today()
        codes = set()

        top_signals = (
            db.query(Signal)
            .filter(Signal.trade_date == today)
            .order_by(Signal.score.desc())
            .limit(3)
            .all()
        )
        for s in top_signals:
            codes.add(s.code)

        positions = get_active_positions(db)
        for p in positions:
            codes.add(p.code)

        watchlist = db.query(Watchlist).all()
        for w in watchlist:
            codes.add(w.code)

        generated = 0
        for code in codes:
            existing = db.query(AIAnalysis).filter(
                AIAnalysis.code == code, AIAnalysis.trade_date == today
            ).first()
            if existing:
                continue
            result = analyze_stock(db, code)
            db.add(AIAnalysis(
                code=code,
                trade_date=today,
                summary=result["summary"],
                risk=result["risk"],
                suggestion=result["suggestion"],
                market_comment=result["market_comment"],
                llm_provider=settings.llm_provider,
            ))
            db.commit()
            generated += 1

        _log_job(db, "ai_analysis", "success",
                 f"Generated {generated} AI analyses for {len(codes)} stocks",
                 started_at=started, records_collected=generated)
    except Exception as e:
        logger.error(f"AI analysis job failed: {e}", exc_info=True)
        _log_job(db, "ai_analysis", "failed", str(e), started_at=started, error_message=str(e))
    finally:
        db.close()
```

- [ ] **Step 2: Register in setup.py**

In `backend/app/scheduler/setup.py`, add import:

```python
from app.scheduler.jobs import (
    job_ai_analysis,
    job_intraday_check,
    ...
)
```

Add job in `start_scheduler()`:

```python
    scheduler.add_job(
        job_ai_analysis, CronTrigger(hour=15, minute=40), id="ai_analysis", replace_existing=True
    )
```

Update the log message to reflect the new count.

- [ ] **Step 3: Verify import**

Run: `cd backend && python -c "from app.scheduler.setup import start_scheduler; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/app/scheduler/jobs.py backend/app/scheduler/setup.py
git commit -m "feat(p4): add daily AI analysis scheduler job at 15:40"
```

---

### Task 7: Feishu AI Summary Integration

**Files:**
- Modify: `backend/app/services/notify/messages.py`
- Modify: `backend/app/scheduler/jobs.py`

- [ ] **Step 1: Update post-market card builder**

Read `backend/app/services/notify/messages.py`. In the signal loop inside `build_post_market_card`, after the existing per-stock deep-link button, add an AI summary line. The signals list now may include an `ai_summary` key.

After the line that appends the per-stock button, add:

```python
            if sig.get("ai_summary"):
                elements.append({
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": f"🤖 AI: {sig['ai_summary'][:80]}"},
                })
```

- [ ] **Step 2: Update jobs.py to attach AI summaries**

In `job_post_market_analyze`, after the score delta computation (the `for sig in top_signals:` block that adds `score_delta`), add AI summary lookup:

```python
        from app.models.ai import AIAnalysis
        for sig in top_signals:
            ai = db.query(AIAnalysis).filter(
                AIAnalysis.code == sig["code"], AIAnalysis.trade_date == today
            ).first()
            sig["ai_summary"] = ai.summary if ai else ""
```

- [ ] **Step 3: Verify**

Run: `cd backend && python -c "from app.services.notify.messages import build_post_market_card; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/notify/messages.py backend/app/scheduler/jobs.py
git commit -m "feat(p4): append AI summary to Feishu post-market card"
```

---

### Task 8: Frontend — AI 洞察 Page

**Files:**
- Create: `frontend/src/api/ai.ts`
- Create: `frontend/src/views/AIInsightView.vue`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/components/layout/AppSidebar.vue`

- [ ] **Step 1: Create API client**

```typescript
// frontend/src/api/ai.ts
import client from './client'

export interface AIAnalysisItem {
  code: string
  stock_name: string
  score: number
  summary: string | null
  risk: string | null
  suggestion: string | null
  market_comment: string | null
  llm_provider: string
  created_at: string
}

export interface AIDetail {
  code: string
  trade_date: string
  summary: string | null
  risk: string | null
  suggestion: string | null
  market_comment: string | null
}

export function fetchDailyAnalyses() {
  return client.get<AIAnalysisItem[]>('/ai/daily')
}

export function fetchAnalysis(code: string) {
  return client.get<AIDetail>('/ai/' + code)
}

export function generateAnalysis(code: string) {
  return client.post<AIDetail>('/ai/generate/' + code)
}
```

- [ ] **Step 2: Create AIInsightView.vue**

```vue
<!-- frontend/src/views/AIInsightView.vue -->
<template>
  <div class="ai-insight">
    <div class="page-header">
      <h2>AI 洞察</h2>
      <span class="sub">{{ items.length }} 条分析</span>
    </div>

    <div v-if="items.length === 0" class="empty-state">
      <p>暂无 AI 分析数据</p>
      <p class="hint">系统会在每个交易日 15:40 自动生成 TOP 信号、持仓和自选股的分析</p>
    </div>

    <div class="analysis-list">
      <div v-for="item in items" :key="item.code" class="analysis-card" @click="goDetail(item.code)">
        <div class="card-header">
          <div class="stock-info">
            <span class="stock-name">{{ item.stock_name }}</span>
            <span class="stock-code">{{ item.code }}</span>
          </div>
          <span class="score-tag">{{ item.score }}分</span>
        </div>
        <div class="card-body">
          <div class="section" v-if="item.summary">
            <div class="section-label">📌 推荐理由</div>
            <p>{{ item.summary }}</p>
          </div>
          <div class="section" v-if="item.risk">
            <div class="section-label">⚠️ 风险提示</div>
            <p>{{ item.risk }}</p>
          </div>
          <div class="section" v-if="item.suggestion">
            <div class="section-label">💡 操作建议</div>
            <p>{{ item.suggestion }}</p>
          </div>
          <div class="section" v-if="item.market_comment">
            <div class="section-label">🌍 市场环境</div>
            <p>{{ item.market_comment }}</p>
          </div>
        </div>
        <div class="card-footer">
          <span class="provider">{{ item.llm_provider }}</span>
          <span class="time">{{ item.created_at?.slice(11, 16) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { fetchDailyAnalyses, type AIAnalysisItem } from '@/api/ai'

const router = useRouter()
const items = ref<AIAnalysisItem[]>([])

function goDetail(code: string) {
  router.push(`/stock/${code}`)
}

onMounted(async () => {
  try {
    const { data } = await fetchDailyAnalyses()
    items.value = data
  } catch {}
})
</script>

<style scoped>
.page-header { display: flex; align-items: baseline; gap: 12px; margin-bottom: 24px; }
.page-header h2 { font-size: 20px; font-weight: 700; color: var(--color-text); }
.sub { font-size: 14px; color: var(--color-text-secondary); }

.empty-state { text-align: center; padding: 60px 0; color: var(--color-text-secondary); }
.hint { font-size: 13px; margin-top: 8px; }

.analysis-list { display: flex; flex-direction: column; gap: 16px; }

.analysis-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  padding: 20px;
  cursor: pointer;
  transition: border-color 0.2s;
}
.analysis-card:hover { border-color: var(--color-accent); }

.card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.stock-info { display: flex; align-items: baseline; gap: 8px; }
.stock-name { font-size: 16px; font-weight: 700; color: var(--color-text); }
.stock-code { font-size: 13px; color: var(--color-accent); font-variant-numeric: tabular-nums; }
.score-tag {
  font-size: 13px; font-weight: 600; color: var(--color-accent);
  background: rgba(78, 205, 196, 0.1); padding: 4px 10px; border-radius: 6px;
}

.section { margin-bottom: 12px; }
.section-label { font-size: 13px; font-weight: 600; color: var(--color-text-secondary); margin-bottom: 4px; }
.section p { font-size: 14px; color: var(--color-text); line-height: 1.6; margin: 0; }

.card-footer { display: flex; justify-content: space-between; font-size: 12px; color: var(--color-text-secondary); margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--color-border); }
</style>
```

- [ ] **Step 3: Add route**

In `frontend/src/router/index.ts`, add before the `/learn` route:

```typescript
{ path: '/ai', name: 'ai', component: () => import('@/views/AIInsightView.vue') },
```

- [ ] **Step 4: Add sidebar entry**

In `frontend/src/components/layout/AppSidebar.vue`:

Add `MagicStick` to the icon imports:
```typescript
import { ..., MagicStick } from '@element-plus/icons-vue'
```

Add to navItems after "个股对比":
```typescript
{ path: '/ai', label: 'AI 洞察', icon: MagicStick },
```

- [ ] **Step 5: Build frontend**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/ai.ts frontend/src/views/AIInsightView.vue frontend/src/router/index.ts frontend/src/components/layout/AppSidebar.vue
git commit -m "feat(p4): add AI Insight page with sidebar navigation"
```

---

### Task 9: Stock Detail Page — AI Analysis Card

**Files:**
- Modify: `frontend/src/views/StockDetailView.vue`

- [ ] **Step 1: Add AI analysis section to template**

Read `frontend/src/views/StockDetailView.vue`. After the "选股理由" card (`card-reason`), add:

```html
    <!-- AI Analysis -->
    <div class="card card-ai">
      <div class="card-title">🤖 AI 分析</div>
      <div v-if="aiAnalysis && aiAnalysis.summary" class="ai-content">
        <div class="ai-section" v-if="aiAnalysis.summary">
          <span class="ai-label">推荐理由</span>
          <p>{{ aiAnalysis.summary }}</p>
        </div>
        <div class="ai-section" v-if="aiAnalysis.risk">
          <span class="ai-label">风险提示</span>
          <p>{{ aiAnalysis.risk }}</p>
        </div>
        <div class="ai-section" v-if="aiAnalysis.suggestion">
          <span class="ai-label">操作建议</span>
          <p>{{ aiAnalysis.suggestion }}</p>
        </div>
        <div class="ai-section" v-if="aiAnalysis.market_comment">
          <span class="ai-label">市场环境</span>
          <p>{{ aiAnalysis.market_comment }}</p>
        </div>
      </div>
      <div v-else>
        <el-button :loading="aiLoading" @click="handleGenerate" type="primary" plain>
          {{ aiLoading ? '生成中...' : '生成 AI 分析' }}
        </el-button>
      </div>
    </div>
```

- [ ] **Step 2: Add script logic**

Add imports:
```typescript
import { fetchAnalysis, generateAnalysis, type AIDetail } from '@/api/ai'
```

Add refs:
```typescript
const aiAnalysis = ref<AIDetail | null>(null)
const aiLoading = ref(false)
```

In `onMounted`, after the existing data fetch, add:
```typescript
    try {
      const { data: aiData } = await fetchAnalysis(code)
      if (aiData.summary) aiAnalysis.value = aiData
    } catch {}
```

Add handler:
```typescript
async function handleGenerate() {
  aiLoading.value = true
  try {
    const { data } = await generateAnalysis(code)
    aiAnalysis.value = data
  } catch {}
  aiLoading.value = false
}
```

- [ ] **Step 3: Add styles**

```css
.card-ai { }
.ai-content { display: flex; flex-direction: column; gap: 12px; }
.ai-section p { font-size: 14px; color: var(--color-text); line-height: 1.6; margin: 4px 0 0; }
.ai-label { font-size: 13px; font-weight: 600; color: var(--color-accent); }
```

- [ ] **Step 4: Build frontend**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/StockDetailView.vue
git commit -m "feat(p4): add AI analysis card to stock detail page"
```

---

### Task 10: Deploy + Configure

**Operational task — no code changes.**

- [ ] **Step 1: Push all code**

```bash
git push
```

- [ ] **Step 2: Get DeepSeek API key**

Register at https://platform.deepseek.com and create an API key.

- [ ] **Step 3: Update server environment**

Add to the server's `.env` or `docker-compose.yml` environment:

```
DEEPSEEK_API_KEY=sk-your-key-here
```

- [ ] **Step 4: Deploy**

```bash
cd /opt/quantClaw && git pull && sudo bash start.sh
```

- [ ] **Step 5: Test on-demand generation**

```bash
curl -X POST https://quant.azhefuye.online/api/ai/generate/000001 \
  -H "Authorization: Bearer <token>"
```

Expected: JSON with summary, risk, suggestion, market_comment fields.

---

## Summary

| Task | What it delivers |
|------|-----------------|
| 1 | LLM client (DeepSeek + Qwen) |
| 2 | Prompt templates |
| 3 | AIAnalysis database model |
| 4 | Context builder + analyzer |
| 5 | AI API endpoints (daily/get/generate) |
| 6 | Scheduler job at 15:40 |
| 7 | Feishu AI summary integration |
| 8 | AI 洞察 frontend page |
| 9 | Stock detail AI card + generate button |
| 10 | Deploy + configure API key |

Total: **10 tasks**, TDD where applicable.
