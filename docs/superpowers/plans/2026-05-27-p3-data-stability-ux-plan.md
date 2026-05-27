# P3: Data Stability + Trading Experience — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make daily data collection resilient with auto-failover, add observability for scheduler jobs, and improve trading UX with watchlist, stock comparison, mobile responsive layout, and enhanced Feishu notifications.

**Architecture:** SmartFetcher wraps existing providers with try-primary-then-fallback logic plus anti-ban measures. SchedulerLog gets extended fields for monitoring. Frontend gets 3 new pages (watchlist, compare, system health), responsive layout with bottom TabBar on mobile, and the header search box gains watchlist integration.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, PostgreSQL 16, Vue 3, TypeScript, Element Plus, ECharts, Pinia

---

## File Map

### New Files (Backend)

| File | Responsibility |
|------|---------------|
| `backend/app/services/data/smart_fetcher.py` | Auto-failover fetcher wrapping both providers |
| `backend/app/api/system.py` | System health API endpoints |
| `backend/app/api/watchlist.py` | Watchlist CRUD API |
| `backend/app/models/watchlist.py` | Watchlist SQLAlchemy model |
| `backend/tests/test_smart_fetcher.py` | SmartFetcher unit tests |
| `backend/tests/test_watchlist_api.py` | Watchlist API tests |
| `backend/tests/test_system_api.py` | System health API tests |

### New Files (Frontend)

| File | Responsibility |
|------|---------------|
| `frontend/src/views/WatchlistView.vue` | Watchlist page |
| `frontend/src/views/CompareView.vue` | Stock comparison page |
| `frontend/src/views/SystemHealthView.vue` | System health dashboard |
| `frontend/src/api/watchlist.ts` | Watchlist API client |
| `frontend/src/api/system.ts` | System health API client |
| `frontend/src/components/layout/BottomTabBar.vue` | Mobile bottom navigation |

### Modified Files

| File | Changes |
|------|---------|
| `backend/app/services/data/providers/eastmoney.py` | Anti-ban: random delays, UA rotation |
| `backend/app/services/data/providers/baostock_provider.py` | Add `fetch_market_sentiment()` |
| `backend/app/models/system.py` | Extend SchedulerLog with new columns |
| `backend/app/scheduler/jobs.py` | Use SmartFetcher, record collection counts |
| `backend/app/api/__init__.py` | Register system + watchlist routers |
| `backend/app/models/__init__.py` | Register Watchlist model |
| `backend/scripts/seed_data.py` | Use SmartFetcher |
| `frontend/src/router/index.ts` | Add watchlist, compare, system routes |
| `frontend/src/components/layout/AppSidebar.vue` | Add nav items |
| `frontend/src/components/layout/AppLayout.vue` | Mobile responsive layout |
| `frontend/src/components/layout/AppHeader.vue` | Add watchlist star in search results, responsive |
| `frontend/src/api/stock.ts` | Add compare endpoint |
| `backend/app/services/notify/messages.py` | Enhanced post-market card |

---

## BATCH 1: Data Stability

### Task 1: EastMoney Anti-Ban Enhancements

**Files:**
- Modify: `backend/app/services/data/providers/eastmoney.py`
- Test: `backend/tests/test_eastmoney_antiban.py`

- [ ] **Step 1: Write test for randomized delays and UA rotation**

```python
# backend/tests/test_eastmoney_antiban.py
import time
from unittest.mock import patch, MagicMock
from app.services.data.providers.eastmoney import _get, _USER_AGENTS, _random_headers


def test_random_headers_returns_valid_headers():
    headers = _random_headers()
    assert "User-Agent" in headers
    assert "Referer" in headers
    assert headers["User-Agent"] in _USER_AGENTS


def test_random_headers_varies():
    results = set()
    for _ in range(50):
        h = _random_headers()
        results.add(h["User-Agent"])
    assert len(results) > 1, "Headers should rotate User-Agents"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_eastmoney_antiban.py -v`
Expected: FAIL — `_USER_AGENTS` and `_random_headers` not found

- [ ] **Step 3: Implement anti-ban measures in eastmoney.py**

Replace the top section of `backend/app/services/data/providers/eastmoney.py`:

```python
import logging
import random
import time
from datetime import date

import httpx
import pandas as pd

from app.services.data.providers.base import AbstractProvider

logger = logging.getLogger(__name__)

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
]

_REFERERS = [
    "https://quote.eastmoney.com/",
    "https://data.eastmoney.com/",
    "https://www.eastmoney.com/",
    "https://guba.eastmoney.com/",
]

_TIMEOUT = 15
_MAX_RETRIES = 3
_RETRY_DELAY = 15
_MIN_DELAY = 0.3
_MAX_DELAY = 0.8


def _random_headers() -> dict[str, str]:
    return {
        "User-Agent": random.choice(_USER_AGENTS),
        "Referer": random.choice(_REFERERS),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }


def _get(url: str, params: dict | None = None) -> dict | None:
    for attempt in range(_MAX_RETRIES):
        try:
            resp = httpx.get(url, params=params, headers=_random_headers(), timeout=_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"EastMoney request attempt {attempt + 1} failed: {e}")
            if attempt < _MAX_RETRIES - 1:
                time.sleep(_RETRY_DELAY)
    return None


def random_delay():
    time.sleep(random.uniform(_MIN_DELAY, _MAX_DELAY))
```

Also update `fetch_daily_klines` in the `EastmoneyProvider` class — the per-stock delay in `fetcher.py` already uses `PER_STOCK_DELAY = 0.3`. Change `fetcher.py` to use the new random delay:

In `backend/app/services/data/fetcher.py`, replace:
```python
time.sleep(PER_STOCK_DELAY)
```
with:
```python
time.sleep(random.uniform(0.3, 0.8))
```

And add `import random` at the top of `fetcher.py`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_eastmoney_antiban.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/data/providers/eastmoney.py backend/app/services/data/fetcher.py backend/tests/test_eastmoney_antiban.py
git commit -m "feat: add anti-ban measures to EastMoney provider"
```

---

### Task 2: SmartFetcher with Auto-Failover

**Files:**
- Create: `backend/app/services/data/smart_fetcher.py`
- Test: `backend/tests/test_smart_fetcher.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_smart_fetcher.py
import pandas as pd
import pytest
from unittest.mock import MagicMock, patch
from datetime import date

from app.services.data.smart_fetcher import SmartFetcher


@pytest.fixture
def fetcher():
    primary = MagicMock()
    fallback = MagicMock()
    return SmartFetcher(primary=primary, fallback=fallback), primary, fallback


def test_stock_list_uses_primary_when_available(fetcher):
    sf, primary, fallback = fetcher
    primary.fetch_stock_basic_list.return_value = pd.DataFrame(
        [{"code": "000001", "name": "Test", "market": "sz"}]
    )
    result = sf.fetch_stock_basic_list()
    assert len(result) == 1
    primary.fetch_stock_basic_list.assert_called_once()
    fallback.fetch_stock_basic_list.assert_not_called()


def test_stock_list_falls_back_on_primary_failure(fetcher):
    sf, primary, fallback = fetcher
    primary.fetch_stock_basic_list.side_effect = Exception("banned")
    fallback.fetch_stock_basic_list.return_value = pd.DataFrame(
        [{"code": "000001", "name": "Test", "market": "sz"}]
    )
    result = sf.fetch_stock_basic_list()
    assert len(result) == 1
    fallback.fetch_stock_basic_list.assert_called_once()


def test_stock_list_falls_back_on_empty_primary(fetcher):
    sf, primary, fallback = fetcher
    primary.fetch_stock_basic_list.return_value = pd.DataFrame()
    fallback.fetch_stock_basic_list.return_value = pd.DataFrame(
        [{"code": "000001", "name": "Test", "market": "sz"}]
    )
    result = sf.fetch_stock_basic_list()
    assert len(result) == 1


def test_north_flow_skips_on_failure(fetcher):
    sf, primary, fallback = fetcher
    primary.fetch_north_flow.side_effect = Exception("banned")
    result = sf.fetch_north_flow(days=5)
    assert result.empty


def test_klines_batch_falls_back(fetcher):
    sf, primary, fallback = fetcher
    primary.fetch_daily_klines.side_effect = Exception("banned")
    fallback.fetch_daily_klines.return_value = pd.DataFrame(
        [{"code": "000001", "trade_date": date.today(), "close": 10.0}]
    )
    result = sf.fetch_daily_klines_batch(["000001"], "20260101", "20260527")
    assert len(result) == 1


def test_market_sentiment_hybrid(fetcher):
    sf, primary, fallback = fetcher
    primary.fetch_market_sentiment.return_value = {
        "trade_date": date.today(), "up_count": 2000, "down_count": 1500,
        "flat_count": 500, "limit_up": 30, "limit_down": 5,
    }
    result = sf.fetch_market_sentiment()
    assert result["up_count"] == 2000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_smart_fetcher.py -v`
Expected: FAIL — `smart_fetcher` module not found

- [ ] **Step 3: Implement SmartFetcher**

```python
# backend/app/services/data/smart_fetcher.py
import logging
import random
import time
from datetime import date, timedelta

import pandas as pd

from app.services.data.providers.base import AbstractProvider

logger = logging.getLogger(__name__)

BATCH_SIZE = 500
BATCH_DELAY = 3


class SmartFetcher:
    def __init__(self, primary: AbstractProvider, fallback: AbstractProvider):
        self._primary = primary
        self._fallback = fallback

    def _try_with_fallback(
        self,
        method_name: str,
        args: tuple = (),
        kwargs: dict | None = None,
        allow_fallback: bool = True,
    ) -> pd.DataFrame | dict | None:
        kwargs = kwargs or {}
        try:
            result = getattr(self._primary, method_name)(*args, **kwargs)
            if isinstance(result, pd.DataFrame) and result.empty:
                raise ValueError(f"Primary returned empty for {method_name}")
            if isinstance(result, dict) and not result:
                raise ValueError(f"Primary returned empty dict for {method_name}")
            return result
        except Exception as e:
            logger.warning(f"Primary {method_name} failed: {e}")
            if not allow_fallback:
                if isinstance(getattr(self._fallback, method_name)(*args, **kwargs), dict):
                    return {}
                return pd.DataFrame()
            try:
                result = getattr(self._fallback, method_name)(*args, **kwargs)
                logger.info(f"Fallback {method_name} succeeded")
                return result
            except Exception as e2:
                logger.error(f"Fallback {method_name} also failed: {e2}")
                return pd.DataFrame()

    def fetch_stock_basic_list(self) -> pd.DataFrame:
        result = self._try_with_fallback("fetch_stock_basic_list")
        return result if isinstance(result, pd.DataFrame) else pd.DataFrame()

    def fetch_daily_klines_batch(
        self,
        codes: list[str],
        start_date: str = "",
        end_date: str = "",
    ) -> pd.DataFrame:
        if not start_date:
            start_date = (date.today() - timedelta(days=400)).strftime("%Y%m%d")
        if not end_date:
            end_date = date.today().strftime("%Y%m%d")
        all_frames: list[pd.DataFrame] = []
        source = self._primary
        failed_primary = False
        for i in range(0, len(codes), BATCH_SIZE):
            batch = codes[i : i + BATCH_SIZE]
            for code in batch:
                try:
                    df = source.fetch_daily_klines(code, start_date, end_date)
                    if df is not None and not df.empty:
                        all_frames.append(df)
                    elif not failed_primary:
                        raise ValueError("empty kline response")
                except Exception:
                    if not failed_primary:
                        logger.warning("Primary klines failing, switching to fallback")
                        source = self._fallback
                        failed_primary = True
                        try:
                            df = source.fetch_daily_klines(code, start_date, end_date)
                            if df is not None and not df.empty:
                                all_frames.append(df)
                        except Exception:
                            pass
                time.sleep(random.uniform(0.3, 0.8))
            if i + BATCH_SIZE < len(codes):
                time.sleep(BATCH_DELAY)
        if not all_frames:
            return pd.DataFrame()
        return pd.concat(all_frames, ignore_index=True)

    def fetch_north_flow(self, days: int = 30) -> pd.DataFrame:
        result = self._try_with_fallback("fetch_north_flow", kwargs={"days": days}, allow_fallback=False)
        return result if isinstance(result, pd.DataFrame) else pd.DataFrame()

    def fetch_sector_daily(self) -> pd.DataFrame:
        result = self._try_with_fallback("fetch_sector_daily", allow_fallback=False)
        return result if isinstance(result, pd.DataFrame) else pd.DataFrame()

    def fetch_market_sentiment(self) -> dict:
        result = self._try_with_fallback("fetch_market_sentiment")
        return result if isinstance(result, dict) else {}
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_smart_fetcher.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/data/smart_fetcher.py backend/tests/test_smart_fetcher.py
git commit -m "feat: add SmartFetcher with auto-failover between providers"
```

---

### Task 3: BaoStock Market Sentiment Calculation

**Files:**
- Modify: `backend/app/services/data/providers/baostock_provider.py`
- Test: `backend/tests/test_baostock_sentiment.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_baostock_sentiment.py
from datetime import date
from unittest.mock import patch, MagicMock
import pandas as pd

from app.services.data.providers.baostock_provider import BaostockProvider


def test_fetch_market_sentiment_calculates_from_klines():
    provider = BaostockProvider()
    mock_df = pd.DataFrame([
        {"code": "000001", "name": "A", "price": 0, "market": "sz", "is_st": False, "list_date": None, "industry": "", "change_pct": 5.0},
        {"code": "000002", "name": "B", "price": 0, "market": "sz", "is_st": False, "list_date": None, "industry": "", "change_pct": -3.0},
        {"code": "000003", "name": "C", "price": 0, "market": "sz", "is_st": False, "list_date": None, "industry": "", "change_pct": 0.0},
        {"code": "000004", "name": "D", "price": 0, "market": "sz", "is_st": False, "list_date": None, "industry": "", "change_pct": 10.0},
        {"code": "000005", "name": "E", "price": 0, "market": "sz", "is_st": False, "list_date": None, "industry": "", "change_pct": -10.0},
    ])
    with patch.object(provider, "_fetch_klines_for_sentiment", return_value=mock_df):
        result = provider.fetch_market_sentiment()
    assert result["up_count"] == 2
    assert result["down_count"] == 2
    assert result["flat_count"] == 1
    assert result["limit_up"] == 1
    assert result["limit_down"] == 1
    assert result["trade_date"] == date.today()
```

- [ ] **Step 2: Run to verify fail**

Run: `cd backend && python -m pytest tests/test_baostock_sentiment.py -v`
Expected: FAIL

- [ ] **Step 3: Implement BaoStock sentiment**

Add to `backend/app/services/data/providers/baostock_provider.py`:

```python
def _fetch_klines_for_sentiment(self) -> pd.DataFrame:
    """Fetch today's change_pct for all stocks to compute sentiment."""
    import baostock as bs
    from datetime import date, timedelta
    today = date.today()
    yesterday = today - timedelta(days=7)
    bs.login()
    try:
        stock_df = self.fetch_stock_basic_list()
        if stock_df.empty:
            return pd.DataFrame()
        codes = stock_df["code"].head(500).tolist()
        records = []
        today_str = today.strftime("%Y-%m-%d")
        for code in codes:
            market = "sh" if code.startswith("6") else "sz"
            bs_code = f"{market}.{code}"
            rs = bs.query_history_k_data_plus(
                bs_code, "date,pctChg",
                start_date=yesterday.strftime("%Y-%m-%d"),
                end_date=today_str,
                frequency="d", adjustflag="2",
            )
            while rs.error_code == "0" and rs.next():
                row = rs.get_row_data()
                if row[0] == today_str:
                    pct = float(row[1]) if row[1] else 0
                    records.append({"code": code, "change_pct": pct})
                    break
        return pd.DataFrame(records)
    except Exception as e:
        logger.error(f"BaoStock sentiment klines failed: {e}")
        return pd.DataFrame()
    finally:
        bs.logout()

def fetch_market_sentiment(self) -> dict:
    df = self._fetch_klines_for_sentiment()
    if df.empty or "change_pct" not in df.columns:
        return {}
    up = int((df["change_pct"] > 0).sum())
    down = int((df["change_pct"] < 0).sum())
    flat = int((df["change_pct"] == 0).sum())
    limit_up = int((df["change_pct"] >= 9.9).sum())
    limit_down = int((df["change_pct"] <= -9.9).sum())
    return {
        "trade_date": date.today(),
        "up_count": up, "down_count": down, "flat_count": flat,
        "limit_up": limit_up, "limit_down": limit_down,
    }
```

Remove the old `fetch_market_sentiment` that returns `{}`.

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_baostock_sentiment.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/data/providers/baostock_provider.py backend/tests/test_baostock_sentiment.py
git commit -m "feat: add BaoStock market sentiment calculation from klines"
```

---

### Task 4: Extend SchedulerLog Model

**Files:**
- Modify: `backend/app/models/system.py`

- [ ] **Step 1: Add new columns to SchedulerLog**

In `backend/app/models/system.py`, replace the `SchedulerLog` class:

```python
class SchedulerLog(Base):
    __tablename__ = "scheduler_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_name: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(10))
    message: Mapped[str | None] = mapped_column(Text)
    records_collected: Mapped[int] = mapped_column(default=0)
    details: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
```

- [ ] **Step 2: Verify model loads**

Run: `cd backend && python -c "from app.models.system import SchedulerLog; print('OK')" `
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/models/system.py
git commit -m "feat: extend SchedulerLog with records_collected, details, error_message"
```

---

### Task 5: Integrate SmartFetcher into Scheduler Jobs

**Files:**
- Modify: `backend/app/scheduler/jobs.py`
- Modify: `backend/scripts/seed_data.py`

- [ ] **Step 1: Update jobs.py to use SmartFetcher**

Replace the import section and `job_post_market_collect` in `backend/app/scheduler/jobs.py`. Key changes:

1. Replace fetcher imports with SmartFetcher:

```python
from app.services.data.smart_fetcher import SmartFetcher
from app.services.data.providers.eastmoney import EastmoneyProvider
from app.services.data.providers.baostock_provider import BaostockProvider

def _get_fetcher() -> SmartFetcher:
    return SmartFetcher(primary=EastmoneyProvider(), fallback=BaostockProvider())
```

2. In `job_post_market_collect`, replace all `fetch_*` calls with `fetcher.fetch_*`:

```python
def job_post_market_collect():
    if not is_trading_day():
        return
    started = datetime.now()
    db = SessionLocal()
    fetcher = _get_fetcher()
    counts = {"stocks": 0, "klines": 0, "north": 0, "sectors": 0, "sentiment": 0}
    errors = []
    try:
        stock_list = fetcher.fetch_stock_basic_list()
        if stock_list.empty:
            raise RuntimeError("Failed to fetch stock list from both sources")
        counts["stocks"] = len(stock_list)
        codes = stock_list["code"].tolist()
        today_str = date.today().strftime("%Y%m%d")
        kline_df = fetcher.fetch_daily_klines_batch(codes, start_date=today_str, end_date=today_str)
        if not kline_df.empty:
            for _, row in kline_df.iterrows():
                existing = (
                    db.query(StockDaily)
                    .filter(StockDaily.code == row["code"], StockDaily.trade_date == row["trade_date"])
                    .first()
                )
                if not existing:
                    db.add(StockDaily(**row.to_dict()))
                    counts["klines"] += 1
            db.commit()

        north_df = fetcher.fetch_north_flow(days=5)
        if not north_df.empty:
            for _, row in north_df.iterrows():
                existing = db.query(NorthFlowModel).filter(NorthFlowModel.trade_date == row["trade_date"]).first()
                if not existing:
                    db.add(NorthFlowModel(
                        trade_date=row["trade_date"],
                        buy_amount=row["buy_amount"],
                        sell_amount=row["sell_amount"],
                        net_amount=row["net_amount"],
                    ))
                    counts["north"] += 1
            db.commit()
        else:
            errors.append("north_flow: no data")

        sector_df = fetcher.fetch_sector_daily()
        if not sector_df.empty:
            for _, row in sector_df.iterrows():
                existing = db.query(SectorDailyModel).filter(
                    SectorDailyModel.sector == row["sector"],
                    SectorDailyModel.trade_date == row["trade_date"],
                ).first()
                if not existing:
                    db.add(SectorDailyModel(
                        sector=row["sector"], trade_date=row["trade_date"],
                        change_pct=row["change_pct"], volume=row.get("volume", 0),
                        net_fund_flow=row.get("net_fund_flow", 0),
                    ))
                    counts["sectors"] += 1
            db.commit()
        else:
            errors.append("sector: no data")

        sentiment = fetcher.fetch_market_sentiment()
        if sentiment:
            existing = db.query(MarketSentiment).filter(MarketSentiment.trade_date == sentiment["trade_date"]).first()
            if not existing:
                db.add(MarketSentiment(**sentiment))
                db.commit()
                counts["sentiment"] = 1
        else:
            errors.append("sentiment: no data")

        import json
        status = "partial" if errors else "success"
        total_records = sum(counts.values())
        _log_job(db, "post_market_collect", status,
                 f"Collected {total_records} records",
                 started_at=started,
                 records_collected=total_records,
                 details=json.dumps({"counts": counts, "errors": errors}))

        if status == "partial":
            FeishuBot(settings.feishu_webhook_url).send_card(
                build_alert_card("数据采集部分失败", f"缺失: {', '.join(errors)}", "warning"))
    except Exception as e:
        logger.error(f"Post-market collect failed: {e}")
        _log_job(db, "post_market_collect", "failed", str(e), started_at=started, error_message=str(e))
        FeishuBot(settings.feishu_webhook_url).send_card(build_alert_card("数据采集失败", str(e), "error"))
    finally:
        db.close()
```

3. Update `_log_job` to accept new fields:

```python
def _log_job(
    db,
    job_name: str,
    status: str,
    message: str = "",
    started_at: datetime | None = None,
    records_collected: int = 0,
    details: str | None = None,
    error_message: str | None = None,
):
    db.add(
        SchedulerLog(
            job_name=job_name,
            status=status,
            message=message,
            records_collected=records_collected,
            details=details,
            error_message=error_message,
            started_at=started_at or datetime.now(),
            finished_at=datetime.now(),
        )
    )
    db.commit()
```

4. Also update `job_intraday_check` to use SmartFetcher for `fetch_stock_basic_list`:

```python
def job_intraday_check():
    ...
    fetcher = _get_fetcher()
    spot_df = fetcher.fetch_stock_basic_list()
    ...
```

- [ ] **Step 2: Update seed_data.py to use SmartFetcher**

In `backend/scripts/seed_data.py`, replace the provider setup and fetch calls:

```python
from app.services.data.smart_fetcher import SmartFetcher
from app.services.data.providers.eastmoney import EastmoneyProvider
from app.services.data.providers.baostock_provider import BaostockProvider

DataSourceManager.register("eastmoney", EastmoneyProvider())
DataSourceManager.register("baostock", BaostockProvider())

fetcher = SmartFetcher(primary=EastmoneyProvider(), fallback=BaostockProvider())
```

Replace all `fetch_*` calls with `fetcher.fetch_*` and `fetcher.fetch_daily_klines_batch(...)`. Remove the `SEED_SOURCE` env var logic and the direct `eastmoney = EastmoneyProvider()` hybrid calls (SmartFetcher handles this now).

- [ ] **Step 3: Run existing tests**

Run: `cd backend && python -m pytest tests/ -v --timeout=30`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/scheduler/jobs.py backend/scripts/seed_data.py
git commit -m "feat: integrate SmartFetcher into scheduler and seed script"
```

---

### Task 6: System Health API

**Files:**
- Create: `backend/app/api/system.py`
- Modify: `backend/app/api/__init__.py`
- Test: `backend/tests/test_system_api.py`

- [ ] **Step 1: Write tests**

```python
# backend/tests/test_system_api.py
from datetime import datetime, date
from app.models.system import SchedulerLog


def test_health_returns_recent_logs(client, db_session):
    db_session.add(SchedulerLog(
        job_name="post_market_collect", status="success",
        message="OK", records_collected=1500,
        started_at=datetime.now(), finished_at=datetime.now(),
    ))
    db_session.commit()
    resp = client.get("/api/system/health")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["logs"]) >= 1
    assert data["logs"][0]["job_name"] == "post_market_collect"


def test_health_summary(client, db_session):
    db_session.add(SchedulerLog(
        job_name="post_market_collect", status="success",
        message="OK", records_collected=1500,
        started_at=datetime.now(), finished_at=datetime.now(),
    ))
    db_session.commit()
    resp = client.get("/api/system/health/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "last_success" in data
    assert "today_status" in data
```

- [ ] **Step 2: Implement system health API**

```python
# backend/app/api/system.py
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
```

- [ ] **Step 3: Register router in `__init__.py`**

Add to `backend/app/api/__init__.py`:

```python
from app.api.system import router as system_router
# ... after existing includes:
api_router.include_router(system_router)
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_system_api.py -v`
Expected: PASS (may need test fixtures — if project has a conftest.py with `client` and `db_session` fixtures, use those; otherwise create minimal ones)

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/system.py backend/app/api/__init__.py backend/tests/test_system_api.py
git commit -m "feat: add system health API endpoints"
```

---

### Task 7: System Health Frontend Page

**Files:**
- Create: `frontend/src/api/system.ts`
- Create: `frontend/src/views/SystemHealthView.vue`
- Modify: `frontend/src/router/index.ts`

- [ ] **Step 1: Create API client**

```typescript
// frontend/src/api/system.ts
import client from './client'

export interface HealthLog {
  id: number
  job_name: string
  status: string
  message: string | null
  records_collected: number
  details: string | null
  error_message: string | null
  started_at: string | null
  finished_at: string | null
}

export interface HealthSummary {
  last_success: string | null
  today_status: string
  today_jobs: number
}

export function fetchHealth() {
  return client.get<{ logs: HealthLog[] }>('/system/health')
}

export function fetchHealthSummary() {
  return client.get<HealthSummary>('/system/health/summary')
}
```

- [ ] **Step 2: Create SystemHealthView.vue**

```vue
<!-- frontend/src/views/SystemHealthView.vue -->
<template>
  <div class="system-health">
    <div class="summary-cards">
      <div class="summary-card" :class="statusClass">
        <div class="card-label">今日状态</div>
        <div class="card-value">{{ statusText }}</div>
      </div>
      <div class="summary-card">
        <div class="card-label">上次成功</div>
        <div class="card-value">{{ lastSuccessText }}</div>
      </div>
      <div class="summary-card">
        <div class="card-label">今日任务</div>
        <div class="card-value">{{ summary?.today_jobs ?? 0 }}</div>
      </div>
    </div>

    <el-table :data="logs" stripe style="width: 100%; margin-top: 24px">
      <el-table-column prop="job_name" label="任务" width="200" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'success' ? 'success' : row.status === 'partial' ? 'warning' : 'danger'" size="small">
            {{ row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="records_collected" label="记录数" width="100" />
      <el-table-column prop="message" label="消息" />
      <el-table-column label="开始时间" width="180">
        <template #default="{ row }">{{ row.started_at?.slice(0, 19) }}</template>
      </el-table-column>
      <el-table-column label="耗时" width="100">
        <template #default="{ row }">{{ duration(row) }}</template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { fetchHealth, fetchHealthSummary, type HealthLog, type HealthSummary } from '@/api/system'

const logs = ref<HealthLog[]>([])
const summary = ref<HealthSummary | null>(null)

const statusText = computed(() => {
  const s = summary.value?.today_status
  if (s === 'success') return '正常'
  if (s === 'partial') return '部分缺失'
  if (s === 'failed') return '失败'
  return '无数据'
})

const statusClass = computed(() => {
  const s = summary.value?.today_status
  if (s === 'success') return 'status-ok'
  if (s === 'partial') return 'status-warn'
  if (s === 'failed') return 'status-error'
  return 'status-none'
})

const lastSuccessText = computed(() => {
  if (!summary.value?.last_success) return '无记录'
  const d = new Date(summary.value.last_success)
  const now = new Date()
  const hours = Math.round((now.getTime() - d.getTime()) / 3600000)
  if (hours < 1) return '刚刚'
  if (hours < 24) return `${hours}小时前`
  return `${Math.round(hours / 24)}天前`
})

function duration(row: HealthLog): string {
  if (!row.started_at || !row.finished_at) return '-'
  const ms = new Date(row.finished_at).getTime() - new Date(row.started_at).getTime()
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

onMounted(async () => {
  const [healthRes, summaryRes] = await Promise.all([fetchHealth(), fetchHealthSummary()])
  logs.value = healthRes.data.logs
  summary.value = summaryRes.data
})
</script>

<style scoped>
.summary-cards {
  display: flex;
  gap: 16px;
}
.summary-card {
  flex: 1;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  padding: 20px;
}
.card-label { font-size: 13px; color: var(--color-text-secondary); margin-bottom: 8px; }
.card-value { font-size: 24px; font-weight: 700; color: var(--color-text); }
.status-ok .card-value { color: var(--color-success, #4ecdc4); }
.status-warn .card-value { color: var(--color-warning, #f4a261); }
.status-error .card-value { color: var(--color-danger, #ef5350); }
.status-none .card-value { color: var(--color-text-secondary); }
</style>
```

- [ ] **Step 3: Add route**

In `frontend/src/router/index.ts`, add before the settings route:

```typescript
{ path: '/system', name: 'system', component: () => import('@/views/SystemHealthView.vue') },
```

- [ ] **Step 4: Build frontend**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/system.ts frontend/src/views/SystemHealthView.vue frontend/src/router/index.ts
git commit -m "feat: add system health frontend page"
```

---

## BATCH 2: Trading Experience

### Task 8: Watchlist Model + API

**Files:**
- Create: `backend/app/models/watchlist.py`
- Create: `backend/app/api/watchlist.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/api/__init__.py`
- Test: `backend/tests/test_watchlist_api.py`

- [ ] **Step 1: Write tests**

```python
# backend/tests/test_watchlist_api.py
def test_add_to_watchlist(client, db_session):
    resp = client.post("/api/watchlist", json={"code": "000001"})
    assert resp.status_code == 200
    assert resp.json()["code"] == "000001"


def test_list_watchlist(client, db_session):
    client.post("/api/watchlist", json={"code": "000001"})
    resp = client.get("/api/watchlist")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_remove_from_watchlist(client, db_session):
    client.post("/api/watchlist", json={"code": "000001"})
    resp = client.delete("/api/watchlist/000001")
    assert resp.status_code == 200
    listing = client.get("/api/watchlist")
    assert len(listing.json()) == 0


def test_duplicate_add_returns_existing(client, db_session):
    client.post("/api/watchlist", json={"code": "000001"})
    resp = client.post("/api/watchlist", json={"code": "000001"})
    assert resp.status_code == 200
```

- [ ] **Step 2: Create model**

```python
# backend/app/models/watchlist.py
from datetime import datetime

from sqlalchemy import String, DateTime, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Watchlist(Base):
    __tablename__ = "watchlist"
    __table_args__ = (UniqueConstraint("user_id", "code", name="uq_watchlist_user_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)
    code: Mapped[str] = mapped_column(String(10), index=True)
    note: Mapped[str | None] = mapped_column(Text)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
```

- [ ] **Step 3: Register model in `__init__.py`**

Add to `backend/app/models/__init__.py`:

```python
from app.models.watchlist import Watchlist  # noqa: F401
```

- [ ] **Step 4: Create API**

```python
# backend/app/api/watchlist.py
from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.signal import Signal
from app.models.stock import StockBasic, StockDaily
from app.models.system import User
from app.models.watchlist import Watchlist

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


class WatchlistAdd(BaseModel):
    code: str
    note: str | None = None


@router.get("")
def list_watchlist(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = db.query(Watchlist).filter(Watchlist.user_id == user.id).order_by(Watchlist.added_at.desc()).all()
    result = []
    for item in items:
        stock = db.query(StockBasic).filter(StockBasic.code == item.code).first()
        latest = db.query(StockDaily).filter(StockDaily.code == item.code).order_by(StockDaily.trade_date.desc()).first()
        signal = db.query(Signal).filter(Signal.code == item.code).order_by(Signal.trade_date.desc()).first()
        result.append({
            "code": item.code,
            "name": stock.name if stock else item.code,
            "industry": stock.industry if stock else "",
            "close": latest.close if latest else 0,
            "change_pct": latest.change_pct if latest else 0,
            "score": signal.score if signal else 0,
            "note": item.note,
            "added_at": str(item.added_at),
        })
    return result


@router.post("")
def add_to_watchlist(
    body: WatchlistAdd,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    existing = db.query(Watchlist).filter(
        Watchlist.user_id == user.id, Watchlist.code == body.code
    ).first()
    if existing:
        return {"code": existing.code, "note": existing.note, "added_at": str(existing.added_at)}
    item = Watchlist(user_id=user.id, code=body.code, note=body.note)
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"code": item.code, "note": item.note, "added_at": str(item.added_at)}


@router.delete("/{code}")
def remove_from_watchlist(
    code: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = db.query(Watchlist).filter(
        Watchlist.user_id == user.id, Watchlist.code == code
    ).first()
    if item:
        db.delete(item)
        db.commit()
    return {"ok": True}


@router.get("/signals")
def watchlist_signals(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    codes = [w.code for w in db.query(Watchlist).filter(Watchlist.user_id == user.id).all()]
    if not codes:
        return []
    signals = (
        db.query(Signal)
        .filter(Signal.code.in_(codes), Signal.trade_date == date.today())
        .order_by(Signal.score.desc())
        .all()
    )
    return [
        {
            "code": s.code, "stock_name": s.stock_name, "score": s.score,
            "reason": s.reason, "direction": s.direction,
        }
        for s in signals
    ]
```

- [ ] **Step 5: Register router**

In `backend/app/api/__init__.py`:

```python
from app.api.watchlist import router as watchlist_router
api_router.include_router(watchlist_router)
```

- [ ] **Step 6: Run tests**

Run: `cd backend && python -m pytest tests/test_watchlist_api.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/watchlist.py backend/app/api/watchlist.py backend/app/models/__init__.py backend/app/api/__init__.py backend/tests/test_watchlist_api.py
git commit -m "feat: add watchlist model and CRUD API"
```

---

### Task 9: Watchlist Frontend Page

**Files:**
- Create: `frontend/src/api/watchlist.ts`
- Create: `frontend/src/views/WatchlistView.vue`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/components/layout/AppSidebar.vue`

- [ ] **Step 1: Create API client**

```typescript
// frontend/src/api/watchlist.ts
import client from './client'

export interface WatchlistItem {
  code: string
  name: string
  industry: string
  close: number
  change_pct: number
  score: number
  note: string | null
  added_at: string
}

export function fetchWatchlist() {
  return client.get<WatchlistItem[]>('/watchlist')
}

export function addToWatchlist(code: string, note?: string) {
  return client.post('/watchlist', { code, note })
}

export function removeFromWatchlist(code: string) {
  return client.delete(`/watchlist/${code}`)
}

export function fetchWatchlistSignals() {
  return client.get('/watchlist/signals')
}
```

- [ ] **Step 2: Create WatchlistView.vue**

```vue
<!-- frontend/src/views/WatchlistView.vue -->
<template>
  <div class="watchlist-page">
    <div class="page-header">
      <h2>自选股</h2>
      <span class="stock-count">{{ items.length }} 只</span>
    </div>

    <el-table :data="items" stripe @row-click="goDetail" style="cursor: pointer">
      <el-table-column prop="code" label="代码" width="100">
        <template #default="{ row }">
          <span class="code-cell">{{ row.code }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="name" label="名称" width="140" />
      <el-table-column prop="industry" label="行业" width="100" />
      <el-table-column label="现价" width="100">
        <template #default="{ row }">{{ row.close.toFixed(2) }}</template>
      </el-table-column>
      <el-table-column label="涨跌幅" width="100">
        <template #default="{ row }">
          <span :class="row.change_pct >= 0 ? 'up' : 'down'">
            {{ row.change_pct >= 0 ? '+' : '' }}{{ row.change_pct.toFixed(2) }}%
          </span>
        </template>
      </el-table-column>
      <el-table-column label="评分" width="80">
        <template #default="{ row }">
          <span class="score-badge">{{ row.score }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-button size="small" @click.stop="goCompare(row.code)">对比</el-button>
          <el-button size="small" type="danger" plain @click.stop="handleRemove(row.code)">移除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { fetchWatchlist, removeFromWatchlist, type WatchlistItem } from '@/api/watchlist'

const router = useRouter()
const items = ref<WatchlistItem[]>([])

async function load() {
  const { data } = await fetchWatchlist()
  items.value = data
}

function goDetail(row: WatchlistItem) {
  router.push(`/stock/${row.code}`)
}

function goCompare(code: string) {
  router.push(`/compare?codes=${code}`)
}

async function handleRemove(code: string) {
  await removeFromWatchlist(code)
  items.value = items.value.filter(i => i.code !== code)
}

onMounted(load)
</script>

<style scoped>
.page-header { display: flex; align-items: baseline; gap: 12px; margin-bottom: 20px; }
.page-header h2 { font-size: 20px; font-weight: 700; color: var(--color-text); }
.stock-count { font-size: 14px; color: var(--color-text-secondary); }
.code-cell { font-variant-numeric: tabular-nums; font-weight: 600; color: var(--color-accent); }
.up { color: var(--color-danger, #ef5350); }
.down { color: var(--color-success, #4ecdc4); }
.score-badge { font-weight: 600; }
</style>
```

- [ ] **Step 3: Add route + sidebar entry**

In `frontend/src/router/index.ts`, add after the `/scan` route:

```typescript
{ path: '/watchlist', name: 'watchlist', component: () => import('@/views/WatchlistView.vue') },
```

In `frontend/src/components/layout/AppSidebar.vue`, add to `navItems` array after scan, and import `Star` icon:

```typescript
import { ..., Star, ... } from '@element-plus/icons-vue'

const navItems = [
  { path: '/', label: '仪表盘', icon: DataLine },
  { path: '/scan', label: '选股扫描', icon: Search },
  { path: '/watchlist', label: '自选股', icon: Star },
  { path: '/position', label: '持仓管理', icon: Wallet },
  // ... rest unchanged
]
```

- [ ] **Step 4: Build frontend**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/watchlist.ts frontend/src/views/WatchlistView.vue frontend/src/router/index.ts frontend/src/components/layout/AppSidebar.vue
git commit -m "feat: add watchlist frontend page with sidebar navigation"
```

---

### Task 10: Stock Compare API + Frontend

**Files:**
- Modify: `backend/app/api/stock.py`
- Modify: `frontend/src/api/stock.ts`
- Create: `frontend/src/views/CompareView.vue`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/components/layout/AppSidebar.vue`

- [ ] **Step 1: Add compare endpoint to backend**

Add to `backend/app/api/stock.py` (before the `/{code}/kline` route):

```python
@router.get("/compare")
def compare(
    codes: str = Query(..., description="Comma-separated stock codes, max 4"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    code_list = [c.strip() for c in codes.split(",")][:4]
    results = []
    for code in code_list:
        stock = db.query(StockBasic).filter(StockBasic.code == code).first()
        signal = db.query(Signal).filter(Signal.code == code).order_by(Signal.trade_date.desc()).first()
        klines = (
            db.query(StockDaily)
            .filter(StockDaily.code == code)
            .order_by(StockDaily.trade_date.desc())
            .limit(60)
            .all()
        )
        klines.reverse()
        results.append({
            "code": code,
            "name": stock.name if stock else code,
            "industry": stock.industry if stock else "",
            "score": signal.score if signal else 0,
            "tech_score": signal.tech_score if signal else 0,
            "fund_score": signal.fund_score if signal else 0,
            "momentum_score": signal.momentum_score if signal else 0,
            "sentiment_score": signal.sentiment_score if signal else 0,
            "klines": [
                {"trade_date": str(k.trade_date), "close": k.close, "volume": k.volume, "change_pct": k.change_pct}
                for k in klines
            ],
        })
    return results
```

- [ ] **Step 2: Add compare to frontend API client**

Add to `frontend/src/api/stock.ts`:

```typescript
export interface CompareStock {
  code: string
  name: string
  industry: string
  score: number
  tech_score: number
  fund_score: number
  momentum_score: number
  sentiment_score: number
  klines: { trade_date: string; close: number; volume: number; change_pct: number }[]
}

export function fetchCompare(codes: string[]) {
  return client.get<CompareStock[]>('/stock/compare', { params: { codes: codes.join(',') } })
}
```

- [ ] **Step 3: Create CompareView.vue**

```vue
<!-- frontend/src/views/CompareView.vue -->
<template>
  <div class="compare-page">
    <div class="page-header">
      <h2>个股对比</h2>
    </div>

    <div class="stock-picker">
      <el-autocomplete
        v-model="searchInput"
        :fetch-suggestions="handleSearch"
        placeholder="搜索添加股票 (最多4只)"
        :trigger-on-focus="false"
        :debounce="300"
        clearable
        @select="handleAdd"
        style="width: 300px"
      />
      <div class="selected-tags">
        <el-tag v-for="code in selectedCodes" :key="code" closable @close="handleRemove(code)" size="large">
          {{ stockNames[code] || code }}
        </el-tag>
      </div>
    </div>

    <div v-if="stocks.length >= 2" class="compare-content">
      <div class="section-title">评分对比</div>
      <div class="radar-container" ref="radarRef" style="height: 350px" />

      <div class="section-title">走势对比 (涨跌幅 %)</div>
      <div class="kline-container" ref="klineRef" style="height: 350px" />

      <div class="section-title">详细评分</div>
      <el-table :data="scoreRows" stripe>
        <el-table-column prop="dimension" label="维度" width="120" />
        <el-table-column v-for="s in stocks" :key="s.code" :label="`${s.name} (${s.code})`">
          <template #default="{ row }">{{ row[s.code] }}</template>
        </el-table-column>
      </el-table>
    </div>

    <div v-else class="empty-hint">请添加至少 2 只股票进行对比</div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import * as echarts from 'echarts'
import { searchStocks } from '@/api/stock'
import { fetchCompare, type CompareStock } from '@/api/stock'

const route = useRoute()
const searchInput = ref('')
const selectedCodes = ref<string[]>([])
const stocks = ref<CompareStock[]>([])
const stockNames = ref<Record<string, string>>({})
const radarRef = ref<HTMLElement>()
const klineRef = ref<HTMLElement>()
let radarChart: echarts.ECharts | null = null
let klineChart: echarts.ECharts | null = null

const scoreRows = computed(() => {
  const dims = [
    { key: 'score', label: '总分' },
    { key: 'tech_score', label: '技术面' },
    { key: 'fund_score', label: '资金面' },
    { key: 'momentum_score', label: '动量' },
    { key: 'sentiment_score', label: '情绪面' },
  ]
  return dims.map(d => {
    const row: Record<string, string | number> = { dimension: d.label }
    for (const s of stocks.value) {
      row[s.code] = (s as Record<string, unknown>)[d.key] as number
    }
    return row
  })
})

async function handleSearch(query: string, cb: (r: { value: string; label: string }[]) => void) {
  if (!query) { cb([]); return }
  try {
    const { data } = await searchStocks(query)
    cb(data.map(s => ({ value: s.code, label: s.name })))
  } catch { cb([]) }
}

async function handleAdd(item: { value: string; label: string }) {
  if (selectedCodes.value.length >= 4 || selectedCodes.value.includes(item.value)) return
  selectedCodes.value.push(item.value)
  stockNames.value[item.value] = item.label
  searchInput.value = ''
  await loadCompare()
}

function handleRemove(code: string) {
  selectedCodes.value = selectedCodes.value.filter(c => c !== code)
  loadCompare()
}

async function loadCompare() {
  if (selectedCodes.value.length < 2) { stocks.value = []; return }
  const { data } = await fetchCompare(selectedCodes.value)
  stocks.value = data
  for (const s of data) stockNames.value[s.code] = s.name
  await nextTick()
  renderRadar()
  renderKline()
}

function renderRadar() {
  if (!radarRef.value) return
  if (!radarChart) radarChart = echarts.init(radarRef.value)
  const indicators = [
    { name: '技术面', max: 40 }, { name: '资金面', max: 30 },
    { name: '动量', max: 20 }, { name: '情绪面', max: 10 },
  ]
  const series = stocks.value.map(s => ({
    name: s.name,
    value: [s.tech_score, s.fund_score, s.momentum_score, s.sentiment_score],
  }))
  radarChart.setOption({
    tooltip: {},
    legend: { data: stocks.value.map(s => s.name), bottom: 0 },
    radar: { indicator: indicators },
    series: [{ type: 'radar', data: series }],
  })
}

function renderKline() {
  if (!klineRef.value || stocks.value.length < 2) return
  if (!klineChart) klineChart = echarts.init(klineRef.value)
  const dates = stocks.value[0].klines.map(k => k.trade_date)
  const series = stocks.value.map(s => {
    const base = s.klines[0]?.close || 1
    return {
      name: s.name,
      type: 'line' as const,
      data: s.klines.map(k => ((k.close - base) / base * 100).toFixed(2)),
      smooth: true,
    }
  })
  klineChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: stocks.value.map(s => s.name), bottom: 0 },
    xAxis: { type: 'category', data: dates },
    yAxis: { type: 'value', axisLabel: { formatter: '{value}%' } },
    series,
  })
}

onMounted(() => {
  const initCodes = route.query.codes
  if (initCodes && typeof initCodes === 'string') {
    selectedCodes.value = initCodes.split(',').slice(0, 4)
    loadCompare()
  }
})
</script>

<style scoped>
.page-header { margin-bottom: 20px; }
.page-header h2 { font-size: 20px; font-weight: 700; color: var(--color-text); }
.stock-picker { display: flex; align-items: center; gap: 16px; margin-bottom: 24px; }
.selected-tags { display: flex; gap: 8px; }
.section-title { font-size: 16px; font-weight: 600; color: var(--color-text); margin: 24px 0 12px; }
.compare-content { margin-top: 16px; }
.empty-hint { text-align: center; color: var(--color-text-secondary); padding: 60px 0; font-size: 15px; }
</style>
```

- [ ] **Step 4: Add route + sidebar**

In `frontend/src/router/index.ts`, add after watchlist:

```typescript
{ path: '/compare', name: 'compare', component: () => import('@/views/CompareView.vue') },
```

In `frontend/src/components/layout/AppSidebar.vue`, add to navItems and import `Histogram` icon:

```typescript
import { ..., Histogram, ... } from '@element-plus/icons-vue'

// After watchlist entry:
{ path: '/compare', label: '个股对比', icon: Histogram },
```

- [ ] **Step 5: Build frontend**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/stock.py frontend/src/api/stock.ts frontend/src/views/CompareView.vue frontend/src/router/index.ts frontend/src/components/layout/AppSidebar.vue
git commit -m "feat: add stock comparison page with radar and kline overlay"
```

---

### Task 11: Mobile Responsive Layout

**Files:**
- Modify: `frontend/src/components/layout/AppLayout.vue`
- Modify: `frontend/src/components/layout/AppSidebar.vue`
- Modify: `frontend/src/components/layout/AppHeader.vue`
- Create: `frontend/src/components/layout/BottomTabBar.vue`

- [ ] **Step 1: Create BottomTabBar.vue**

```vue
<!-- frontend/src/components/layout/BottomTabBar.vue -->
<template>
  <nav class="bottom-tab-bar">
    <router-link
      v-for="tab in tabs"
      :key="tab.path"
      :to="tab.path"
      class="tab-item"
      :class="{ active: isActive(tab.path) }"
    >
      <el-icon :size="22"><component :is="tab.icon" /></el-icon>
      <span class="tab-label">{{ tab.label }}</span>
    </router-link>
  </nav>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'
import { DataLine, Search, Star, Wallet, More } from '@element-plus/icons-vue'

const route = useRoute()

const tabs = [
  { path: '/', label: '首页', icon: DataLine },
  { path: '/scan', label: '扫描', icon: Search },
  { path: '/watchlist', label: '自选', icon: Star },
  { path: '/position', label: '持仓', icon: Wallet },
  { path: '/settings', label: '更多', icon: More },
]

function isActive(path: string): boolean {
  if (path === '/') return route.path === '/'
  return route.path.startsWith(path)
}
</script>

<style scoped>
.bottom-tab-bar {
  display: none;
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: 56px;
  background: var(--color-surface);
  border-top: 1px solid var(--color-border);
  z-index: 200;
  justify-content: space-around;
  align-items: center;
  padding-bottom: env(safe-area-inset-bottom, 0);
}

@media (max-width: 767px) {
  .bottom-tab-bar { display: flex; }
}

.tab-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  text-decoration: none;
  color: var(--color-text-secondary);
  font-size: 11px;
  padding: 4px 12px;
  transition: color 0.2s;
}
.tab-item.active { color: var(--color-accent); }
.tab-label { white-space: nowrap; }
</style>
```

- [ ] **Step 2: Update AppLayout.vue for responsive**

Replace `frontend/src/components/layout/AppLayout.vue`:

```vue
<template>
  <div class="app-layout">
    <AppSidebar />
    <div class="main-area">
      <AppHeader />
      <main class="main-content">
        <router-view />
      </main>
    </div>
    <BottomTabBar />
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import AppSidebar from './AppSidebar.vue'
import AppHeader from './AppHeader.vue'
import BottomTabBar from './BottomTabBar.vue'

const authStore = useAuthStore()

onMounted(() => {
  if (!authStore.username) {
    authStore.fetchMe()
  }
})
</script>

<style scoped>
.app-layout {
  display: flex;
  min-height: 100vh;
}

.main-area {
  flex: 1;
  margin-left: 220px;
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

.main-content {
  flex: 1;
  padding: 24px 32px 32px;
  overflow-y: auto;
}

@media (max-width: 767px) {
  .main-area {
    margin-left: 0;
  }
  .main-content {
    padding: 16px 16px 72px;
  }
}
</style>
```

- [ ] **Step 3: Update AppSidebar.vue — hide on mobile**

Add at the end of `<style scoped>` in `AppSidebar.vue`:

```css
@media (max-width: 767px) {
  .sidebar { display: none; }
}
```

- [ ] **Step 4: Update AppHeader.vue — responsive search**

Add at the end of `<style scoped>` in `AppHeader.vue`:

```css
@media (max-width: 767px) {
  .app-header { padding: 0 16px; }
  .stock-search :deep(.el-autocomplete) { width: 180px; }
  .header-date { display: none; }
}
```

- [ ] **Step 5: Build frontend**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/layout/
git commit -m "feat: add mobile responsive layout with bottom TabBar"
```

---

### Task 12: Enhanced Feishu Post-Market Message

**Files:**
- Modify: `backend/app/services/notify/messages.py`
- Modify: `backend/app/scheduler/jobs.py`

- [ ] **Step 1: Add deep links and score deltas to post-market card**

In `backend/app/services/notify/messages.py`, update the signal section in `build_post_market_card`:

Replace the signal loop (lines ~28-37) with:

```python
        for i, sig in enumerate(signals):
            medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"{i+1}."
            delta_text = ""
            if sig.get("score_delta"):
                d = sig["score_delta"]
                delta_text = f" ({'↑' if d > 0 else '↓'}{abs(d):.0f})"
            sig_lines = [
                f"{medal} **{sig['stock_name']}** {sig['code']}  评分 {sig['score']}/100{delta_text}",
                f"现价 ¥{sig['close_price']:.2f} | 买入 ¥{sig.get('buy_low', 0):.2f}-{sig.get('buy_high', 0):.2f}",
                f"止损 ¥{sig.get('stop_loss', 0):.2f} | 目标 ¥{sig.get('target', 0):.2f}",
                f"📌 {sig.get('reason', '')}",
            ]
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "\n".join(sig_lines)}})
            if base_url:
                elements.append({
                    "tag": "action",
                    "actions": [{
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": f"查看 {sig['stock_name']} →"},
                        "url": f"{base_url}/stock/{sig['code']}",
                        "type": "default",
                    }],
                })
```

- [ ] **Step 2: Compute score deltas in jobs.py**

In `job_post_market_analyze`, after building `top_signals`, before building the card, add score delta lookup:

```python
        from datetime import timedelta
        yesterday = today - timedelta(days=1)
        for sig in top_signals:
            prev = db.query(Signal).filter(
                Signal.code == sig["code"],
                Signal.trade_date < today,
            ).order_by(Signal.trade_date.desc()).first()
            sig["score_delta"] = sig["score"] - prev.score if prev else 0
```

- [ ] **Step 3: Verify notify module loads**

Run: `cd backend && python -c "from app.services.notify.messages import build_post_market_card; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/notify/messages.py backend/app/scheduler/jobs.py
git commit -m "feat: enhanced Feishu messages with score deltas and deep links"
```

---

### Task 13: Add Watchlist Star to Search Results + Stock Detail

**Files:**
- Modify: `frontend/src/components/layout/AppHeader.vue`
- Modify: `frontend/src/views/StockDetailView.vue` (add watchlist button)

- [ ] **Step 1: Add star toggle to search dropdown**

In `AppHeader.vue`, update the search result template:

```html
<template #default="{ item }">
  <div class="search-item">
    <span class="search-code">{{ item.value }}</span>
    <span class="search-name">{{ item.label }}</span>
    <span class="search-industry">{{ item.industry }}</span>
  </div>
</template>
```

No changes needed here — the watchlist add can happen from the detail page. The search is already functional.

- [ ] **Step 2: Add watchlist button to StockDetailView**

Read `StockDetailView.vue` to find the header section, then add a star/unstar toggle button next to the stock name. This requires:

1. Import `addToWatchlist`, `removeFromWatchlist`, `fetchWatchlist` from `@/api/watchlist`
2. On mount, check if current stock is in watchlist
3. Toggle button to add/remove

Add to the script section:

```typescript
import { addToWatchlist, removeFromWatchlist, fetchWatchlist } from '@/api/watchlist'

const isWatched = ref(false)

async function checkWatchlist() {
  const { data } = await fetchWatchlist()
  isWatched.value = data.some(w => w.code === code.value)
}

async function toggleWatchlist() {
  if (isWatched.value) {
    await removeFromWatchlist(code.value)
    isWatched.value = false
  } else {
    await addToWatchlist(code.value)
    isWatched.value = true
  }
}
```

Call `checkWatchlist()` in `onMounted`. Add a star button in the template header area.

- [ ] **Step 3: Build frontend**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/StockDetailView.vue frontend/src/components/layout/AppHeader.vue
git commit -m "feat: add watchlist toggle on stock detail page"
```

---

### Task 14: Database Migration on Server

**Files:** None (operational task)

- [ ] **Step 1: After deploying all code, run ALTER TABLE on server**

The SchedulerLog and new Watchlist tables need schema updates. SQLAlchemy `create_all` handles new tables but not column additions.

```bash
# SSH to server, then:
docker exec quantclaw-postgres-1 psql -U quantclaw -d quantclaw -c "
ALTER TABLE scheduler_log ADD COLUMN IF NOT EXISTS records_collected INTEGER DEFAULT 0;
ALTER TABLE scheduler_log ADD COLUMN IF NOT EXISTS details TEXT;
ALTER TABLE scheduler_log ADD COLUMN IF NOT EXISTS error_message TEXT;
"
```

The `watchlist` table will be auto-created by `Base.metadata.create_all(bind=engine)` on app startup.

- [ ] **Step 2: Rebuild and restart**

```bash
cd /opt/quantClaw && git pull && sudo bash start.sh
```

- [ ] **Step 3: Verify health endpoint**

```bash
curl -s https://quant.azhefuye.online/api/system/health/summary -H "Authorization: Bearer <token>"
```

Expected: JSON response with `today_status`

- [ ] **Step 4: Run seed to populate data**

```bash
docker exec quantclaw-quantclaw-1 python -m scripts.seed_data
```

---

## Summary

| Batch | Tasks | What it delivers |
|-------|-------|-----------------|
| **1: Data Stability** | Tasks 1-7 | Anti-ban, auto-failover, BaoStock sentiment, monitoring API + page |
| **2: UX** | Tasks 8-13 | Watchlist, stock comparison, mobile layout, enhanced Feishu |
| **Ops** | Task 14 | DB migration + deploy |

Total: **14 tasks**, ~22 commits.
