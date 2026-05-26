# P0+P1: 数据源双源切换 + 实时行情监控 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace AKShare with EastMoney HTTP + BaoStock dual data sources (switchable via UI), and add real-time market monitoring with 60-second refresh during trading hours.

**Architecture:** Provider adapter pattern — `AbstractProvider` defines the interface, `EastmoneyProvider` and `BaostockProvider` implement it, `DataSourceManager` routes calls based on `SystemConfig` DB setting. Realtime data collected by `RealtimeService` via APScheduler interval trigger, cached in memory, exposed via REST API.

**Tech Stack:** FastAPI, SQLAlchemy, APScheduler, httpx, baostock, Vue 3, ECharts, TradingView Lightweight Charts

---

### Task 1: Provider Abstraction + SystemConfig Model

**Files:**
- Create: `backend/app/services/data/providers/__init__.py`
- Create: `backend/app/services/data/providers/base.py`
- Create: `backend/app/models/config.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_provider_base.py`

- [ ] **Step 1: Create SystemConfig model**

```python
# backend/app/models/config.py
from sqlalchemy import Column, String, DateTime, func
from app.database import Base


class SystemConfig(Base):
    __tablename__ = "system_config"

    key = Column(String, primary_key=True)
    value = Column(String, nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
```

- [ ] **Step 2: Register SystemConfig in models/__init__.py**

Add to `backend/app/models/__init__.py`:

```python
from app.models.config import SystemConfig
```

Add `"SystemConfig"` to the `__all__` list.

- [ ] **Step 3: Create provider __init__ and base class**

```python
# backend/app/services/data/providers/__init__.py
from app.services.data.providers.base import AbstractProvider, DataSourceManager

__all__ = ["AbstractProvider", "DataSourceManager"]
```

```python
# backend/app/services/data/providers/base.py
import abc
import logging
from datetime import date

import pandas as pd

from app.database import SessionLocal
from app.models.config import SystemConfig

logger = logging.getLogger(__name__)

_DATA_SOURCE_KEY = "data_source"
_DEFAULT_SOURCE = "eastmoney"


class AbstractProvider(abc.ABC):
    @abc.abstractmethod
    def fetch_stock_basic_list(self) -> pd.DataFrame:
        """Return DataFrame with columns: code, name, price, market, is_st, list_date, industry"""

    @abc.abstractmethod
    def fetch_daily_klines(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Return DataFrame with columns: code, trade_date, open, high, low, close, volume, amount, change_pct"""

    @abc.abstractmethod
    def fetch_north_flow(self, days: int = 30) -> pd.DataFrame:
        """Return DataFrame with columns: trade_date, buy_amount, sell_amount, net_amount"""

    @abc.abstractmethod
    def fetch_sector_daily(self) -> pd.DataFrame:
        """Return DataFrame with columns: sector, trade_date, change_pct, volume, net_fund_flow"""

    @abc.abstractmethod
    def fetch_market_sentiment(self) -> dict:
        """Return dict with keys: trade_date, up_count, down_count, flat_count, limit_up, limit_down"""


class DataSourceManager:
    _providers: dict[str, AbstractProvider] = {}
    _current: str | None = None

    @classmethod
    def register(cls, name: str, provider: AbstractProvider) -> None:
        cls._providers[name] = provider

    @classmethod
    def get_source_name(cls) -> str:
        if cls._current:
            return cls._current
        db = SessionLocal()
        try:
            row = db.query(SystemConfig).filter(SystemConfig.key == _DATA_SOURCE_KEY).first()
            cls._current = row.value if row else _DEFAULT_SOURCE
        finally:
            db.close()
        return cls._current

    @classmethod
    def set_source(cls, name: str) -> None:
        if name not in cls._providers:
            raise ValueError(f"Unknown data source: {name}. Available: {list(cls._providers.keys())}")
        db = SessionLocal()
        try:
            row = db.query(SystemConfig).filter(SystemConfig.key == _DATA_SOURCE_KEY).first()
            if row:
                row.value = name
            else:
                db.add(SystemConfig(key=_DATA_SOURCE_KEY, value=name))
            db.commit()
        finally:
            db.close()
        cls._current = name

    @classmethod
    def get_provider(cls) -> AbstractProvider:
        name = cls.get_source_name()
        if name not in cls._providers:
            logger.warning(f"Provider '{name}' not registered, falling back to '{_DEFAULT_SOURCE}'")
            name = _DEFAULT_SOURCE
        return cls._providers[name]

    @classmethod
    def available_sources(cls) -> list[str]:
        return list(cls._providers.keys())

    @classmethod
    def reset(cls) -> None:
        cls._current = None
```

- [ ] **Step 4: Write test**

```python
# backend/tests/test_provider_base.py
from unittest.mock import patch, MagicMock
import pandas as pd
from app.services.data.providers.base import AbstractProvider, DataSourceManager


class FakeProvider(AbstractProvider):
    def fetch_stock_basic_list(self):
        return pd.DataFrame({"code": ["000001"], "name": ["Test"]})

    def fetch_daily_klines(self, code, start_date, end_date):
        return pd.DataFrame()

    def fetch_north_flow(self, days=30):
        return pd.DataFrame()

    def fetch_sector_daily(self):
        return pd.DataFrame()

    def fetch_market_sentiment(self):
        return {}


def test_register_and_get_provider():
    DataSourceManager._providers.clear()
    DataSourceManager._current = "fake"
    fake = FakeProvider()
    DataSourceManager.register("fake", fake)
    assert DataSourceManager.get_provider() is fake
    assert "fake" in DataSourceManager.available_sources()


def test_get_provider_fallback():
    DataSourceManager._providers.clear()
    DataSourceManager._current = "nonexistent"
    fake = FakeProvider()
    DataSourceManager.register("eastmoney", fake)
    provider = DataSourceManager.get_provider()
    assert provider is fake
```

- [ ] **Step 5: Run tests**

Run: `cd backend && python -m pytest tests/test_provider_base.py -v`
Expected: 2 tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/config.py backend/app/models/__init__.py backend/app/services/data/providers/ backend/tests/test_provider_base.py
git commit -m "feat: add Provider abstraction and SystemConfig model"
```

---

### Task 2: EastmoneyProvider

**Files:**
- Create: `backend/app/services/data/providers/eastmoney.py`
- Test: `backend/tests/test_eastmoney_provider.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_eastmoney_provider.py
from unittest.mock import patch, AsyncMock, MagicMock
import json
import pandas as pd
import pytest
from app.services.data.providers.eastmoney import EastmoneyProvider


@pytest.fixture
def provider():
    return EastmoneyProvider()


def _mock_response(data):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = data
    return resp


class TestFetchStockBasicList:
    def test_parses_eastmoney_response(self, provider):
        mock_data = {
            "data": {
                "diff": [
                    {"f12": "000001", "f14": "平安银行", "f2": 12.5, "f3": 1.2, "f100": "银行"},
                    {"f12": "600000", "f14": "浦发银行", "f2": 8.3, "f3": -0.5, "f100": "银行"},
                ]
            }
        }
        with patch("httpx.get", return_value=_mock_response(mock_data)):
            df = provider.fetch_stock_basic_list()
        assert len(df) == 2
        assert list(df.columns) >= ["code", "name", "price", "market", "is_st"]
        assert df.iloc[0]["code"] == "000001"
        assert df.iloc[0]["market"] == "sz"
        assert df.iloc[1]["market"] == "sh"

    def test_returns_empty_on_failure(self, provider):
        with patch("httpx.get", side_effect=Exception("timeout")):
            df = provider.fetch_stock_basic_list()
        assert df.empty


class TestFetchDailyKlines:
    def test_parses_kline_response(self, provider):
        mock_data = {
            "data": {
                "klines": [
                    "2026-05-20,10.00,10.50,9.90,10.30,50000000,500000000.00,3.00",
                    "2026-05-21,10.30,10.80,10.20,10.60,60000000,600000000.00,2.91",
                ]
            }
        }
        with patch("httpx.get", return_value=_mock_response(mock_data)):
            df = provider.fetch_daily_klines("000001", "20260520", "20260521")
        assert len(df) == 2
        assert df.iloc[0]["close"] == 10.30
        assert df.iloc[0]["code"] == "000001"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_eastmoney_provider.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.data.providers.eastmoney'`

- [ ] **Step 3: Implement EastmoneyProvider**

```python
# backend/app/services/data/providers/eastmoney.py
import logging
import time
from datetime import date

import httpx
import pandas as pd

from app.services.data.providers.base import AbstractProvider

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://quote.eastmoney.com/",
}
_TIMEOUT = 15
_MAX_RETRIES = 3
_RETRY_DELAY = 5


def _get(url: str, params: dict | None = None) -> dict | None:
    for attempt in range(_MAX_RETRIES):
        try:
            resp = httpx.get(url, params=params, headers=_HEADERS, timeout=_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"EastMoney request attempt {attempt + 1} failed: {e}")
            if attempt < _MAX_RETRIES - 1:
                time.sleep(_RETRY_DELAY)
    return None


class EastmoneyProvider(AbstractProvider):
    def fetch_stock_basic_list(self) -> pd.DataFrame:
        url = "http://push2.eastmoney.com/api/qt/clist/get"
        params = {
            "pn": "1", "pz": "6000", "po": "1", "np": "1",
            "fltt": "2", "invt": "2", "fid": "f3",
            "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048",
            "fields": "f2,f3,f12,f14,f100",
        }
        data = _get(url, params)
        if not data or "data" not in data or not data["data"]:
            return pd.DataFrame()
        rows = data["data"].get("diff", [])
        if not rows:
            return pd.DataFrame()
        records = []
        for r in rows:
            code = str(r.get("f12", ""))
            name = str(r.get("f14", ""))
            price = r.get("f2")
            change_pct = r.get("f3")
            industry = r.get("f100", "")
            if not code or price == "-":
                continue
            market = "bj" if code.startswith(("8", "4")) else "sh" if code.startswith("6") else "sz"
            is_st = "ST" in name or "退市" in name
            records.append({
                "code": code, "name": name, "price": float(price) if price else 0,
                "change_pct": float(change_pct) if change_pct and change_pct != "-" else 0,
                "market": market, "is_st": is_st, "list_date": None, "industry": industry,
            })
        return pd.DataFrame(records)

    def fetch_daily_klines(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        market = "1" if code.startswith("6") else "0"
        secid = f"{market}.{code}"
        url = "http://push2his.eastmoney.com/api/qt/stock/kline/get"
        params = {
            "secid": secid, "klt": "101", "fqt": "1",
            "beg": start_date, "end": end_date,
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        }
        data = _get(url, params)
        if not data or "data" not in data or not data["data"]:
            return pd.DataFrame()
        klines = data["data"].get("klines", [])
        if not klines:
            return pd.DataFrame()
        records = []
        for line in klines:
            parts = line.split(",")
            if len(parts) < 8:
                continue
            records.append({
                "code": code,
                "trade_date": pd.to_datetime(parts[0]).date(),
                "open": float(parts[1]),
                "close": float(parts[2]),
                "high": float(parts[3]),
                "low": float(parts[4]),
                "volume": int(float(parts[5])),
                "amount": float(parts[6]),
                "change_pct": float(parts[7]) if parts[7] != "-" else 0,
            })
        return pd.DataFrame(records)

    def fetch_north_flow(self, days: int = 30) -> pd.DataFrame:
        url = "http://push2his.eastmoney.com/api/qt/kamt.kline/get"
        params = {
            "fields1": "f1,f3,f5", "fields2": "f51,f52",
            "klt": "101", "lmt": str(days),
        }
        data = _get(url, params)
        if not data or "data" not in data or not data["data"]:
            return pd.DataFrame()
        s2n = data["data"].get("s2n", [])
        if not s2n:
            return pd.DataFrame()
        records = []
        for line in s2n:
            parts = line.split(",")
            if len(parts) < 2:
                continue
            net = float(parts[1]) if parts[1] != "-" else 0
            records.append({
                "trade_date": pd.to_datetime(parts[0]).date(),
                "net_amount": net,
                "buy_amount": net if net > 0 else 0,
                "sell_amount": abs(net) if net < 0 else 0,
            })
        return pd.DataFrame(records)

    def fetch_sector_daily(self) -> pd.DataFrame:
        url = "http://push2.eastmoney.com/api/qt/clist/get"
        params = {
            "pn": "1", "pz": "100", "po": "1", "np": "1",
            "fltt": "2", "invt": "2", "fid": "f3",
            "fs": "m:90+t:2",
            "fields": "f3,f12,f14,f62",
        }
        data = _get(url, params)
        if not data or "data" not in data or not data["data"]:
            return pd.DataFrame()
        rows = data["data"].get("diff", [])
        records = []
        for r in rows:
            sector = r.get("f14", "")
            change_pct = r.get("f3", 0)
            net_fund = r.get("f62", 0)
            if not sector:
                continue
            records.append({
                "sector": sector,
                "trade_date": date.today(),
                "change_pct": float(change_pct) if change_pct != "-" else 0,
                "volume": 0,
                "net_fund_flow": float(net_fund) if net_fund and net_fund != "-" else 0,
            })
        return pd.DataFrame(records)

    def fetch_market_sentiment(self) -> dict:
        df = self.fetch_stock_basic_list()
        if df.empty or "change_pct" not in df.columns:
            return {}
        up = (df["change_pct"] > 0).sum()
        down = (df["change_pct"] < 0).sum()
        flat = (df["change_pct"] == 0).sum()
        limit_up = (df["change_pct"] >= 9.9).sum()
        limit_down = (df["change_pct"] <= -9.9).sum()
        return {
            "trade_date": date.today(),
            "up_count": int(up), "down_count": int(down), "flat_count": int(flat),
            "limit_up": int(limit_up), "limit_down": int(limit_down),
        }
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_eastmoney_provider.py -v`
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/data/providers/eastmoney.py backend/tests/test_eastmoney_provider.py
git commit -m "feat: add EastmoneyProvider with HTTP direct API calls"
```

---

### Task 3: BaostockProvider

**Files:**
- Create: `backend/app/services/data/providers/baostock_provider.py`
- Test: `backend/tests/test_baostock_provider.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_baostock_provider.py
from unittest.mock import patch, MagicMock
import pandas as pd
import pytest
from app.services.data.providers.baostock_provider import BaostockProvider


@pytest.fixture
def provider():
    return BaostockProvider()


def test_fetch_stock_basic_list(provider):
    mock_rs = MagicMock()
    mock_rs.error_code = "0"
    result_df = pd.DataFrame({
        "code": ["sh.600000", "sz.000001"],
        "code_name": ["浦发银行", "平安银行"],
        "ipoDate": ["1999-11-10", "1991-04-03"],
        "industry": ["银行", "银行"],
        "type": ["1", "1"],
        "status": ["1", "1"],
    })
    with patch("baostock.login"), \
         patch("baostock.logout"), \
         patch("baostock.query_stock_basic", return_value=mock_rs), \
         patch.object(mock_rs, "__class__", create=True), \
         patch("baostock.query_stock_basic") as mock_query:
        mock_query.return_value = mock_rs
        with patch.object(provider, "_query_stock_list", return_value=result_df):
            df = provider.fetch_stock_basic_list()
    assert len(df) == 2
    assert "code" in df.columns
    assert df.iloc[0]["market"] == "sh"


def test_north_flow_returns_empty(provider):
    df = provider.fetch_north_flow()
    assert df.empty


def test_sector_daily_returns_empty(provider):
    df = provider.fetch_sector_daily()
    assert df.empty


def test_market_sentiment_returns_empty(provider):
    result = provider.fetch_market_sentiment()
    assert result == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_baostock_provider.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement BaostockProvider**

```python
# backend/app/services/data/providers/baostock_provider.py
import logging
from datetime import date, timedelta

import pandas as pd

from app.services.data.providers.base import AbstractProvider

logger = logging.getLogger(__name__)


class BaostockProvider(AbstractProvider):
    def _query_stock_list(self) -> pd.DataFrame:
        import baostock as bs
        bs.login()
        try:
            rs = bs.query_stock_basic()
            rows = []
            while rs.error_code == "0" and rs.next():
                rows.append(rs.get_row_data())
            return pd.DataFrame(rows, columns=rs.fields)
        finally:
            bs.logout()

    def fetch_stock_basic_list(self) -> pd.DataFrame:
        try:
            df = self._query_stock_list()
        except Exception as e:
            logger.error(f"BaoStock fetch_stock_basic_list failed: {e}")
            return pd.DataFrame()
        if df.empty:
            return pd.DataFrame()
        df = df[df["status"] == "1"].copy()
        df["code"] = df["code"].str.replace("sh.", "").str.replace("sz.", "").str.replace("bj.", "")
        df["market"] = df["code"].apply(
            lambda c: "bj" if c.startswith(("8", "4")) else "sh" if c.startswith("6") else "sz"
        )
        df["name"] = df.get("code_name", "")
        df["is_st"] = df["name"].str.contains(r"ST|退市", case=False, na=False)
        df["list_date"] = pd.to_datetime(df.get("ipoDate"), errors="coerce").dt.date
        df["price"] = 0
        df["industry"] = df.get("industry", "")
        return df[["code", "name", "price", "market", "is_st", "list_date", "industry"]].copy()

    def fetch_daily_klines(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        import baostock as bs
        market = "sh" if code.startswith("6") else "sz"
        bs_code = f"{market}.{code}"
        start_fmt = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
        end_fmt = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}"
        bs.login()
        try:
            rs = bs.query_history_k_data_plus(
                bs_code, "date,open,high,low,close,volume,amount,pctChg",
                start_date=start_fmt, end_date=end_fmt,
                frequency="d", adjustflag="2",
            )
            rows = []
            while rs.error_code == "0" and rs.next():
                rows.append(rs.get_row_data())
            if not rows:
                return pd.DataFrame()
            df = pd.DataFrame(rows, columns=rs.fields)
            df = df.rename(columns={"date": "trade_date", "pctChg": "change_pct"})
            df["code"] = code
            df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
            for col in ["open", "high", "low", "close", "amount", "change_pct"]:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
            df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0).astype(int)
            return df[["code", "trade_date", "open", "high", "low", "close", "volume", "amount", "change_pct"]]
        except Exception as e:
            logger.error(f"BaoStock fetch_daily_klines failed for {code}: {e}")
            return pd.DataFrame()
        finally:
            bs.logout()

    def fetch_north_flow(self, days: int = 30) -> pd.DataFrame:
        return pd.DataFrame()

    def fetch_sector_daily(self) -> pd.DataFrame:
        return pd.DataFrame()

    def fetch_market_sentiment(self) -> dict:
        return {}
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_baostock_provider.py -v`
Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/data/providers/baostock_provider.py backend/tests/test_baostock_provider.py
git commit -m "feat: add BaostockProvider for historical K-line data"
```

---

### Task 4: Refactor fetcher.py + Register Providers

**Files:**
- Modify: `backend/app/services/data/fetcher.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_fetcher.py`

- [ ] **Step 1: Refactor fetcher.py to delegate to providers**

Replace the entire content of `backend/app/services/data/fetcher.py`:

```python
import logging
import time
from datetime import date, timedelta

import pandas as pd

from app.services.data.providers.base import DataSourceManager

logger = logging.getLogger(__name__)

BATCH_SIZE = 500
BATCH_DELAY = 3


def fetch_stock_basic_list() -> pd.DataFrame:
    provider = DataSourceManager.get_provider()
    df = provider.fetch_stock_basic_list()
    if df is None:
        return pd.DataFrame()
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

    provider = DataSourceManager.get_provider()
    all_frames = []
    for i in range(0, len(codes), BATCH_SIZE):
        batch = codes[i:i + BATCH_SIZE]
        for code in batch:
            df = provider.fetch_daily_klines(code, start_date, end_date)
            if df is not None and not df.empty:
                all_frames.append(df)
        if i + BATCH_SIZE < len(codes):
            time.sleep(BATCH_DELAY)

    if not all_frames:
        return pd.DataFrame()
    return pd.concat(all_frames, ignore_index=True)


def fetch_north_flow(days: int = 30) -> pd.DataFrame:
    provider = DataSourceManager.get_provider()
    df = provider.fetch_north_flow(days)
    if df is None:
        return pd.DataFrame()
    return df


def fetch_sector_daily() -> pd.DataFrame:
    provider = DataSourceManager.get_provider()
    df = provider.fetch_sector_daily()
    if df is None:
        return pd.DataFrame()
    return df


def fetch_market_sentiment() -> dict:
    provider = DataSourceManager.get_provider()
    result = provider.fetch_market_sentiment()
    if result is None:
        return {}
    return result
```

- [ ] **Step 2: Register providers at startup in main.py**

Add provider registration to `backend/app/main.py` in the `lifespan` function, before `start_scheduler()`:

```python
from app.services.data.providers.base import DataSourceManager
from app.services.data.providers.eastmoney import EastmoneyProvider
from app.services.data.providers.baostock_provider import BaostockProvider
```

In the `lifespan` function, after `_seed_admin()` and before `start_scheduler()`:

```python
    DataSourceManager.register("eastmoney", EastmoneyProvider())
    DataSourceManager.register("baostock", BaostockProvider())
```

- [ ] **Step 3: Update test_fetcher.py to mock the provider**

Replace `backend/tests/test_fetcher.py`:

```python
from unittest.mock import patch, MagicMock
import pandas as pd
import pytest
from app.services.data.providers.base import AbstractProvider, DataSourceManager
from app.services.data.fetcher import fetch_stock_basic_list, fetch_daily_klines_batch, fetch_north_flow


class MockProvider(AbstractProvider):
    def fetch_stock_basic_list(self):
        return pd.DataFrame({
            "code": ["000001", "600000"],
            "name": ["平安银行", "浦发银行"],
            "price": [12.5, 8.3],
            "market": ["sz", "sh"],
            "is_st": [False, False],
            "list_date": [None, None],
            "industry": ["银行", "银行"],
        })

    def fetch_daily_klines(self, code, start_date, end_date):
        return pd.DataFrame({
            "code": [code], "trade_date": ["2026-05-20"],
            "open": [10.0], "high": [10.5], "low": [9.9],
            "close": [10.3], "volume": [50000000],
            "amount": [500000000.0], "change_pct": [3.0],
        })

    def fetch_north_flow(self, days=30):
        return pd.DataFrame({
            "trade_date": ["2026-05-20"],
            "buy_amount": [1e9], "sell_amount": [0], "net_amount": [1e9],
        })

    def fetch_sector_daily(self):
        return pd.DataFrame()

    def fetch_market_sentiment(self):
        return {"trade_date": "2026-05-20", "up_count": 3000, "down_count": 1500}


@pytest.fixture(autouse=True)
def setup_mock_provider():
    DataSourceManager._providers.clear()
    DataSourceManager._current = "mock"
    DataSourceManager.register("mock", MockProvider())
    yield
    DataSourceManager._providers.clear()


def test_fetch_stock_basic_list():
    df = fetch_stock_basic_list()
    assert len(df) == 2
    assert "code" in df.columns


def test_fetch_daily_klines_batch():
    df = fetch_daily_klines_batch(["000001", "600000"], "20260501", "20260520")
    assert len(df) == 2


def test_fetch_north_flow():
    df = fetch_north_flow(days=30)
    assert len(df) == 1
    assert "net_amount" in df.columns
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_fetcher.py -v`
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/data/fetcher.py backend/app/main.py backend/tests/test_fetcher.py
git commit -m "refactor: fetcher delegates to pluggable Provider via DataSourceManager"
```

---

### Task 5: Fix trading_calendar.py

**Files:**
- Modify: `backend/app/scheduler/trading_calendar.py`
- Test: `backend/tests/test_trading_calendar.py`

- [ ] **Step 1: Write test**

```python
# backend/tests/test_trading_calendar.py
from datetime import date
from app.scheduler.trading_calendar import is_trading_day


def test_weekend_is_not_trading_day():
    saturday = date(2026, 5, 23)
    sunday = date(2026, 5, 24)
    assert not is_trading_day(saturday)
    assert not is_trading_day(sunday)


def test_weekday_is_trading_day():
    monday = date(2026, 5, 25)
    assert is_trading_day(monday)


def test_known_holiday():
    national_day = date(2026, 10, 1)
    assert not is_trading_day(national_day)
```

- [ ] **Step 2: Replace trading_calendar.py (remove AKShare dependency)**

```python
# backend/app/scheduler/trading_calendar.py
import logging
from datetime import date

logger = logging.getLogger(__name__)

HOLIDAYS_2025 = {
    date(2025, 1, 1),
    *[date(2025, 1, d) for d in range(28, 32)],
    *[date(2025, 2, d) for d in range(1, 5)],
    date(2025, 4, 4), date(2025, 4, 5), date(2025, 4, 7),
    date(2025, 5, 1), date(2025, 5, 2), date(2025, 5, 5),
    date(2025, 6, 2),
    date(2025, 10, 1), date(2025, 10, 2), date(2025, 10, 3),
    date(2025, 10, 6), date(2025, 10, 7), date(2025, 10, 8),
}

HOLIDAYS_2026 = {
    date(2026, 1, 1), date(2026, 1, 2),
    date(2026, 2, 16), date(2026, 2, 17), date(2026, 2, 18),
    date(2026, 2, 19), date(2026, 2, 20), date(2026, 2, 23), date(2026, 2, 24),
    date(2026, 4, 6),
    date(2026, 5, 1), date(2026, 5, 4), date(2026, 5, 5),
    date(2026, 6, 19),
    date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 5),
    date(2026, 10, 6), date(2026, 10, 7), date(2026, 10, 8), date(2026, 10, 9),
}

HOLIDAYS_2027 = {
    date(2027, 1, 1),
    date(2027, 2, 8), date(2027, 2, 9), date(2027, 2, 10),
    date(2027, 2, 11), date(2027, 2, 12),
    date(2027, 4, 5),
    date(2027, 5, 3),
    date(2027, 6, 14),
    date(2027, 10, 1), date(2027, 10, 4), date(2027, 10, 5),
    date(2027, 10, 6), date(2027, 10, 7),
}

_ALL_HOLIDAYS = HOLIDAYS_2025 | HOLIDAYS_2026 | HOLIDAYS_2027


def is_trading_day(d: date | None = None) -> bool:
    if d is None:
        d = date.today()
    if d.weekday() >= 5:
        return False
    return d not in _ALL_HOLIDAYS
```

- [ ] **Step 3: Run tests**

Run: `cd backend && python -m pytest tests/test_trading_calendar.py -v`
Expected: 3 tests PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/scheduler/trading_calendar.py backend/tests/test_trading_calendar.py
git commit -m "fix: replace AKShare trading calendar with built-in holiday list"
```

---

### Task 6: Data Source Settings API

**Files:**
- Modify: `backend/app/api/settings.py`
- Modify: `backend/app/schemas/settings.py`
- Test: `backend/tests/test_settings_api.py`

- [ ] **Step 1: Add schemas**

Add to `backend/app/schemas/settings.py`:

```python
class DataSourceSettings(BaseModel):
    source: str
    available: list[str] = []
```

- [ ] **Step 2: Add API endpoints**

Add to `backend/app/api/settings.py`:

```python
from app.services.data.providers.base import DataSourceManager
from app.schemas.settings import DataSourceSettings
```

Add these endpoints:

```python
@router.get("/data-source", response_model=DataSourceSettings)
def get_data_source(user: User = Depends(get_current_user)):
    return DataSourceSettings(
        source=DataSourceManager.get_source_name(),
        available=DataSourceManager.available_sources(),
    )


@router.put("/data-source", response_model=DataSourceSettings)
def set_data_source(body: DataSourceSettings, user: User = Depends(get_current_user)):
    DataSourceManager.set_source(body.source)
    return DataSourceSettings(
        source=DataSourceManager.get_source_name(),
        available=DataSourceManager.available_sources(),
    )
```

- [ ] **Step 3: Write test**

```python
# backend/tests/test_settings_api.py
from unittest.mock import patch
from app.services.data.providers.base import DataSourceManager, AbstractProvider
import pandas as pd


class FakeProvider(AbstractProvider):
    def fetch_stock_basic_list(self): return pd.DataFrame()
    def fetch_daily_klines(self, c, s, e): return pd.DataFrame()
    def fetch_north_flow(self, d=30): return pd.DataFrame()
    def fetch_sector_daily(self): return pd.DataFrame()
    def fetch_market_sentiment(self): return {}


def test_get_data_source(client, auth_headers):
    DataSourceManager._providers.clear()
    DataSourceManager._current = "eastmoney"
    DataSourceManager.register("eastmoney", FakeProvider())
    DataSourceManager.register("baostock", FakeProvider())
    resp = client.get("/api/settings/data-source", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == "eastmoney"
    assert "eastmoney" in data["available"]
    assert "baostock" in data["available"]
```

Note: This test requires the `client` and `auth_headers` fixtures from the existing test infrastructure. If they don't exist yet, create a `conftest.py` with FastAPI TestClient and auth token setup.

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_settings_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/settings.py backend/app/schemas/settings.py backend/tests/test_settings_api.py
git commit -m "feat: add data source settings API endpoints"
```

---

### Task 7: Update Dependencies

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Update requirements.txt**

Remove `akshare>=1.16.72` and add `baostock>=0.8.8`.

The updated `backend/requirements.txt`:

```
fastapi==0.115.6
uvicorn[standard]==0.34.0
sqlalchemy==2.0.36
psycopg2-binary==2.9.10
pydantic-settings==2.7.1
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
bcrypt==4.2.1
httpx==0.28.1
baostock>=0.8.8
pandas==2.2.3
apscheduler==3.10.4
python-multipart==0.0.20
```

- [ ] **Step 2: Install locally and verify**

Run: `cd backend && pip install baostock>=0.8.8`

- [ ] **Step 3: Run all existing tests**

Run: `cd backend && python -m pytest -v`
Expected: All tests PASS (no more `import akshare` anywhere except possibly old tests)

- [ ] **Step 4: Commit**

```bash
git add backend/requirements.txt
git commit -m "chore: replace akshare with baostock in dependencies"
```

---

### Task 8: Frontend Data Source Settings

**Files:**
- Modify: `frontend/src/api/settings.ts`
- Modify: `frontend/src/views/SettingsView.vue`

- [ ] **Step 1: Add API functions**

Add to `frontend/src/api/settings.ts`:

```typescript
export interface DataSourceConfig {
  source: string
  available: string[]
}

export function getDataSource() {
  return client.get<DataSourceConfig>('/settings/data-source')
}

export function setDataSource(source: string) {
  return client.put<DataSourceConfig>('/settings/data-source', { source })
}
```

- [ ] **Step 2: Add data source selector to SettingsView.vue**

Add a new section at the top of the settings form in `frontend/src/views/SettingsView.vue`. Insert a "数据源" card before the existing strategy settings section:

```vue
<!-- Data Source Section -->
<div class="card settings-card">
  <h3 class="settings-title">数据源</h3>
  <div class="form-group">
    <label class="form-label">当前数据源</label>
    <select v-model="dataSource" class="form-select" @change="onDataSourceChange">
      <option v-for="src in availableSources" :key="src" :value="src">
        {{ sourceLabels[src] || src }}
      </option>
    </select>
    <p class="form-hint" v-if="dataSource === 'baostock'">
      BaoStock 不支持北向资金和板块数据，这些模块将显示为空。
    </p>
  </div>
</div>
```

Add to `<script setup>`:

```typescript
import { getDataSource, setDataSource } from '@/api/settings'

const dataSource = ref('eastmoney')
const availableSources = ref<string[]>([])
const sourceLabels: Record<string, string> = {
  eastmoney: '东方财富 (推荐)',
  baostock: 'BaoStock',
}

async function loadDataSource() {
  const { data } = await getDataSource()
  dataSource.value = data.source
  availableSources.value = data.available
}

async function onDataSourceChange() {
  await setDataSource(dataSource.value)
}
```

Call `loadDataSource()` in `onMounted`.

- [ ] **Step 3: Verify in browser**

Run dev server, navigate to Settings page. Verify:
- Data source dropdown appears with "东方财富 (推荐)" and "BaoStock" options
- Switching saves correctly (refresh page, should persist)
- BaoStock shows warning hint

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/settings.ts frontend/src/views/SettingsView.vue
git commit -m "feat: add data source selector in settings page"
```

---

### Task 9: RealtimeService Backend

**Files:**
- Create: `backend/app/services/data/realtime.py`
- Test: `backend/tests/test_realtime_service.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_realtime_service.py
from unittest.mock import patch, MagicMock
from datetime import time
from app.services.data.realtime import RealtimeService


def _mock_index_response():
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "data": {
            "diff": [
                {"f12": "000001", "f14": "上证指数", "f2": 3285.62, "f3": 0.83, "f4": 27.12, "f6": 350000000000},
                {"f12": "399001", "f14": "深证成指", "f2": 10521.3, "f3": 1.12, "f4": 116.8, "f6": 480000000000},
                {"f12": "399006", "f14": "创业板指", "f2": 2103.5, "f3": 1.45, "f4": 30.05, "f6": 150000000000},
            ]
        }
    }
    return resp


def test_fetch_indices():
    service = RealtimeService()
    with patch("httpx.get", return_value=_mock_index_response()):
        service.refresh_indices()
    data = service.get_indices()
    assert len(data) == 3
    assert data[0]["name"] == "上证指数"
    assert data[0]["price"] == 3285.62


def test_is_trading_time():
    service = RealtimeService()
    assert service._is_trading_time(time(9, 30))
    assert service._is_trading_time(time(10, 0))
    assert service._is_trading_time(time(14, 0))
    assert not service._is_trading_time(time(12, 0))
    assert not service._is_trading_time(time(8, 0))
    assert not service._is_trading_time(time(15, 30))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_realtime_service.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement RealtimeService**

```python
# backend/app/services/data/realtime.py
import logging
from datetime import datetime, time, date
from typing import Any

import httpx

from app.scheduler.trading_calendar import is_trading_day

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://quote.eastmoney.com/",
}
_TIMEOUT = 10


def _get(url: str, params: dict | None = None) -> dict | None:
    try:
        resp = httpx.get(url, params=params, headers=_HEADERS, timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning(f"Realtime fetch failed: {e}")
        return None


class RealtimeService:
    def __init__(self):
        self._indices: list[dict] = []
        self._north_flow: dict = {}
        self._sectors_top: list[dict] = []
        self._sectors_fund_top: list[dict] = []
        self._positions: list[dict] = []
        self._last_refresh: datetime | None = None
        self._fail_count: int = 0

    def _is_trading_time(self, t: time | None = None) -> bool:
        if t is None:
            t = datetime.now().time()
        morning = time(9, 15) <= t <= time(11, 35)
        afternoon = time(12, 55) <= t <= time(15, 5)
        return morning or afternoon

    def should_refresh(self) -> bool:
        if not is_trading_day():
            return False
        if not self._is_trading_time():
            return False
        if self._fail_count >= 5:
            return False
        return True

    def refresh_indices(self) -> None:
        url = "http://push2.eastmoney.com/api/qt/ulist.np/get"
        params = {
            "fltt": "2", "invt": "2",
            "fields": "f2,f3,f4,f6,f12,f14",
            "secids": "1.000001,0.399001,0.399006",
        }
        data = _get(url, params)
        if not data or "data" not in data or not data["data"]:
            self._fail_count += 1
            return
        rows = data["data"].get("diff", [])
        self._indices = [
            {
                "code": r.get("f12", ""),
                "name": r.get("f14", ""),
                "price": float(r.get("f2", 0)),
                "change_pct": float(r.get("f3", 0)),
                "change_amount": float(r.get("f4", 0)),
                "turnover": float(r.get("f6", 0)),
            }
            for r in rows
        ]
        self._fail_count = 0

    def refresh_north_flow(self) -> None:
        url = "http://push2.eastmoney.com/api/qt/kamt.rtmin/get"
        params = {"fields1": "f1,f2,f3", "fields2": "f51,f52,f54,f56"}
        data = _get(url, params)
        if not data or "data" not in data or not data["data"]:
            return
        s2n = data["data"].get("s2n", [])
        if s2n:
            latest = s2n[-1]
            parts = latest.split(",")
            if len(parts) >= 4:
                net = float(parts[1]) if parts[1] != "-" else 0
                self._north_flow = {
                    "time": parts[0],
                    "net_amount": net,
                    "sh_net": float(parts[2]) if parts[2] != "-" else 0,
                    "sz_net": float(parts[3]) if parts[3] != "-" else 0,
                }
        timeline = []
        if s2n:
            for line in s2n:
                parts = line.split(",")
                if len(parts) >= 2 and parts[1] != "-":
                    timeline.append({"time": parts[0], "net": float(parts[1])})
        self._north_flow["timeline"] = timeline

    def refresh_sectors(self) -> None:
        url = "http://push2.eastmoney.com/api/qt/clist/get"
        # Top gainers
        params_gain = {
            "pn": "1", "pz": "10", "po": "1", "np": "1",
            "fltt": "2", "invt": "2", "fid": "f3",
            "fs": "m:90+t:2", "fields": "f3,f14,f62,f104,f105",
        }
        data = _get(url, params_gain)
        if data and data.get("data"):
            self._sectors_top = [
                {
                    "name": r.get("f14", ""),
                    "change_pct": float(r.get("f3", 0)),
                    "net_fund_flow": float(r.get("f62", 0)) if r.get("f62") and r.get("f62") != "-" else 0,
                    "up_count": int(r.get("f104", 0)),
                    "down_count": int(r.get("f105", 0)),
                }
                for r in data["data"].get("diff", [])
            ]
        # Top fund inflow
        params_fund = {
            "pn": "1", "pz": "10", "po": "1", "np": "1",
            "fltt": "2", "invt": "2", "fid": "f62",
            "fs": "m:90+t:2", "fields": "f3,f14,f62",
        }
        data = _get(url, params_fund)
        if data and data.get("data"):
            self._sectors_fund_top = [
                {
                    "name": r.get("f14", ""),
                    "change_pct": float(r.get("f3", 0)),
                    "net_fund_flow": float(r.get("f62", 0)) if r.get("f62") and r.get("f62") != "-" else 0,
                }
                for r in data["data"].get("diff", [])
            ]

    def refresh_positions(self, position_codes: list[str]) -> None:
        if not position_codes:
            self._positions = []
            return
        secids = ",".join(
            f"{'1' if c.startswith('6') else '0'}.{c}" for c in position_codes
        )
        url = "http://push2.eastmoney.com/api/qt/ulist.np/get"
        params = {
            "fltt": "2", "invt": "2",
            "fields": "f2,f3,f4,f12,f14",
            "secids": secids,
        }
        data = _get(url, params)
        if not data or "data" not in data or not data["data"]:
            return
        self._positions = [
            {
                "code": r.get("f12", ""),
                "name": r.get("f14", ""),
                "price": float(r.get("f2", 0)),
                "change_pct": float(r.get("f3", 0)),
            }
            for r in data["data"].get("diff", [])
        ]

    def refresh_all(self, position_codes: list[str] | None = None) -> None:
        if not self.should_refresh():
            return
        self.refresh_indices()
        self.refresh_north_flow()
        self.refresh_sectors()
        self.refresh_positions(position_codes or [])
        self._last_refresh = datetime.now()
        logger.info("Realtime data refreshed")

    def get_indices(self) -> list[dict]:
        return self._indices

    def get_north_flow(self) -> dict:
        return self._north_flow

    def get_sectors(self) -> dict:
        return {"gainers": self._sectors_top, "fund_inflow": self._sectors_fund_top}

    def get_positions(self) -> list[dict]:
        return self._positions

    def get_summary(self) -> dict:
        return {
            "indices": self._indices,
            "north_flow": self._north_flow,
            "sectors": {"gainers": self._sectors_top[:5], "fund_inflow": self._sectors_fund_top[:5]},
            "is_trading": self._is_trading_time(),
            "last_refresh": self._last_refresh.isoformat() if self._last_refresh else None,
        }


realtime_service = RealtimeService()
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_realtime_service.py -v`
Expected: 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/data/realtime.py backend/tests/test_realtime_service.py
git commit -m "feat: add RealtimeService for live market data collection"
```

---

### Task 10: Realtime API + Scheduler Integration

**Files:**
- Create: `backend/app/api/realtime.py`
- Modify: `backend/app/api/__init__.py`
- Modify: `backend/app/scheduler/setup.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Create realtime API router**

```python
# backend/app/api/realtime.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.position import Position
from app.models.system import User
from app.services.data.realtime import realtime_service

router = APIRouter(prefix="/api/realtime", tags=["realtime"])


@router.get("/indices")
def get_indices(user: User = Depends(get_current_user)):
    return realtime_service.get_indices()


@router.get("/north-flow")
def get_north_flow(user: User = Depends(get_current_user)):
    return realtime_service.get_north_flow()


@router.get("/sectors")
def get_sectors(user: User = Depends(get_current_user)):
    return realtime_service.get_sectors()


@router.get("/positions")
def get_positions(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    open_positions = db.query(Position).filter(Position.status == "open").all()
    live_prices = {p["code"]: p for p in realtime_service.get_positions()}
    result = []
    for pos in open_positions:
        live = live_prices.get(pos.code, {})
        current_price = live.get("price", pos.current_price or pos.buy_price)
        pnl = (current_price - pos.buy_price) * pos.shares
        pnl_pct = (current_price - pos.buy_price) / pos.buy_price * 100 if pos.buy_price else 0
        result.append({
            "code": pos.code,
            "stock_name": pos.stock_name,
            "buy_price": pos.buy_price,
            "current_price": current_price,
            "change_pct": live.get("change_pct", 0),
            "shares": pos.shares,
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "buy_date": pos.buy_date.isoformat() if pos.buy_date else None,
        })
    return result


@router.get("/summary")
def get_summary(user: User = Depends(get_current_user)):
    return realtime_service.get_summary()
```

- [ ] **Step 2: Register router in api/__init__.py**

Add to `backend/app/api/__init__.py`:

```python
from app.api.realtime import router as realtime_router
```

Add: `api_router.include_router(realtime_router)`

- [ ] **Step 3: Add realtime scheduler job**

Add to `backend/app/scheduler/setup.py`:

Import at top:
```python
from apscheduler.triggers.interval import IntervalTrigger
```

Add a new function and register it in `start_scheduler`:

```python
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
```

In `start_scheduler()`, add after the maintenance job:

```python
    scheduler.add_job(
        _job_realtime_refresh, IntervalTrigger(seconds=60),
        id="realtime_refresh", replace_existing=True,
    )
    logger.info("Scheduler started with 6 trading-day jobs + realtime refresh")
```

Update the log message to reflect the new job count.

- [ ] **Step 4: Run full test suite**

Run: `cd backend && python -m pytest -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/realtime.py backend/app/api/__init__.py backend/app/scheduler/setup.py
git commit -m "feat: add realtime API endpoints and 60s scheduler job"
```

---

### Task 11: Frontend Realtime API Module + RealtimeBar

**Files:**
- Create: `frontend/src/api/realtime.ts`
- Create: `frontend/src/components/realtime/RealtimeBar.vue`
- Modify: `frontend/src/views/DashboardView.vue`

- [ ] **Step 1: Create realtime API module**

```typescript
// frontend/src/api/realtime.ts
import client from './client'

export interface IndexData {
  code: string
  name: string
  price: number
  change_pct: number
  change_amount: number
  turnover: number
}

export interface NorthFlowData {
  time: string
  net_amount: number
  sh_net: number
  sz_net: number
  timeline: { time: string; net: number }[]
}

export interface SectorData {
  name: string
  change_pct: number
  net_fund_flow: number
  up_count?: number
  down_count?: number
}

export interface PositionLive {
  code: string
  stock_name: string
  buy_price: number
  current_price: number
  change_pct: number
  shares: number
  pnl: number
  pnl_pct: number
  buy_date: string
}

export interface RealtimeSummary {
  indices: IndexData[]
  north_flow: NorthFlowData
  sectors: { gainers: SectorData[]; fund_inflow: SectorData[] }
  is_trading: boolean
  last_refresh: string | null
}

export function fetchRealtimeSummary() {
  return client.get<RealtimeSummary>('/realtime/summary')
}

export function fetchRealtimeIndices() {
  return client.get<IndexData[]>('/realtime/indices')
}

export function fetchRealtimeNorthFlow() {
  return client.get<NorthFlowData>('/realtime/north-flow')
}

export function fetchRealtimeSectors() {
  return client.get<{ gainers: SectorData[]; fund_inflow: SectorData[] }>('/realtime/sectors')
}

export function fetchRealtimePositions() {
  return client.get<PositionLive[]>('/realtime/positions')
}
```

- [ ] **Step 2: Create RealtimeBar component**

```vue
<!-- frontend/src/components/realtime/RealtimeBar.vue -->
<template>
  <div class="realtime-bar" :class="{ closed: !summary.is_trading }">
    <div class="bar-indices">
      <div v-for="idx in summary.indices" :key="idx.code" class="bar-index">
        <span class="bar-idx-name">{{ idx.name }}</span>
        <span class="bar-idx-price">{{ idx.price.toFixed(2) }}</span>
        <span class="bar-idx-pct" :class="idx.change_pct >= 0 ? 'up' : 'down'">
          {{ idx.change_pct >= 0 ? '+' : '' }}{{ idx.change_pct.toFixed(2) }}%
        </span>
      </div>
    </div>
    <div class="bar-extra">
      <div class="bar-north" v-if="summary.north_flow?.net_amount !== undefined">
        <span class="bar-label">北向</span>
        <span :class="summary.north_flow.net_amount >= 0 ? 'up' : 'down'">
          {{ formatFlow(summary.north_flow.net_amount) }}
        </span>
      </div>
      <div class="bar-status" v-if="!summary.is_trading">
        已收盘
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { fetchRealtimeSummary, type RealtimeSummary } from '@/api/realtime'

const summary = ref<RealtimeSummary>({
  indices: [], north_flow: {} as any,
  sectors: { gainers: [], fund_inflow: [] },
  is_trading: false, last_refresh: null,
})

let timer: ReturnType<typeof setInterval> | null = null

function formatFlow(val: number): string {
  const abs = Math.abs(val)
  const sign = val >= 0 ? '+' : '-'
  if (abs >= 1e8) return `${sign}${(abs / 1e8).toFixed(1)}亿`
  if (abs >= 1e4) return `${sign}${(abs / 1e4).toFixed(0)}万`
  return `${sign}${abs.toFixed(0)}`
}

async function refresh() {
  try {
    const { data } = await fetchRealtimeSummary()
    summary.value = data
  } catch {}
}

onMounted(() => {
  refresh()
  timer = setInterval(refresh, 60_000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.realtime-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  background: var(--color-surface-elevated, #1a1f2e);
  border-radius: 12px;
  margin-bottom: 20px;
  gap: 16px;
  flex-wrap: wrap;
}
.realtime-bar.closed {
  opacity: 0.7;
}
.bar-indices {
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
}
.bar-index {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.bar-idx-name {
  font-size: 13px;
  color: var(--color-text-muted, #8b95a5);
}
.bar-idx-price {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text, #e0e6ed);
}
.bar-idx-pct {
  font-size: 13px;
  font-weight: 500;
}
.bar-extra {
  display: flex;
  gap: 16px;
  align-items: center;
}
.bar-label {
  font-size: 13px;
  color: var(--color-text-muted, #8b95a5);
  margin-right: 4px;
}
.bar-status {
  font-size: 12px;
  color: var(--color-text-muted, #8b95a5);
  background: rgba(255,255,255,0.05);
  padding: 2px 10px;
  border-radius: 4px;
}
.up { color: #ef4444; }
.down { color: #22c55e; }
</style>
```

- [ ] **Step 3: Embed RealtimeBar in DashboardView.vue**

At the top of `<template>` in `DashboardView.vue`, right inside the root `.dashboard` div and before the first `.dash-row`:

```vue
<RealtimeBar />
```

Import in `<script setup>`:

```typescript
import RealtimeBar from '@/components/realtime/RealtimeBar.vue'
```

- [ ] **Step 4: Verify in browser**

Start dev server. Navigate to Dashboard. Verify:
- Realtime bar appears at top with index data (may show empty if outside trading hours)
- Bar shows "已收盘" label when market is closed
- No console errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/realtime.ts frontend/src/components/realtime/RealtimeBar.vue frontend/src/views/DashboardView.vue
git commit -m "feat: add RealtimeBar component to dashboard"
```

---

### Task 12: Frontend Realtime Monitor Page

**Files:**
- Create: `frontend/src/views/RealtimeView.vue`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/components/layout/AppSidebar.vue`

- [ ] **Step 1: Create RealtimeView page**

```vue
<!-- frontend/src/views/RealtimeView.vue -->
<template>
  <div class="realtime-page">
    <h1 class="page-title">实时监控</h1>
    <p class="page-status" :class="{ closed: !summary.is_trading }">
      {{ summary.is_trading ? '交易中' : '已收盘' }}
      <span v-if="summary.last_refresh" class="last-refresh">
        更新于 {{ formatTime(summary.last_refresh) }}
      </span>
    </p>

    <!-- Index Cards -->
    <div class="section index-section">
      <div v-for="idx in summary.indices" :key="idx.code" class="card index-card">
        <div class="idx-name">{{ idx.name }}</div>
        <div class="idx-price" :class="idx.change_pct >= 0 ? 'up' : 'down'">
          {{ idx.price.toFixed(2) }}
        </div>
        <div class="idx-change" :class="idx.change_pct >= 0 ? 'up' : 'down'">
          {{ idx.change_pct >= 0 ? '+' : '' }}{{ idx.change_pct.toFixed(2) }}%
          <span class="idx-amount">{{ idx.change_amount >= 0 ? '+' : '' }}{{ idx.change_amount.toFixed(2) }}</span>
        </div>
      </div>
    </div>

    <!-- North Flow -->
    <div class="section">
      <h2 class="section-title">北向资金</h2>
      <div class="card north-card">
        <div class="north-summary" v-if="northFlow.net_amount !== undefined">
          <div class="north-item">
            <span class="north-label">累计净流入</span>
            <span class="north-val" :class="northFlow.net_amount >= 0 ? 'up' : 'down'">
              {{ formatFlow(northFlow.net_amount) }}
            </span>
          </div>
          <div class="north-item">
            <span class="north-label">沪股通</span>
            <span :class="(northFlow.sh_net || 0) >= 0 ? 'up' : 'down'">{{ formatFlow(northFlow.sh_net || 0) }}</span>
          </div>
          <div class="north-item">
            <span class="north-label">深股通</span>
            <span :class="(northFlow.sz_net || 0) >= 0 ? 'up' : 'down'">{{ formatFlow(northFlow.sz_net || 0) }}</span>
          </div>
        </div>
        <div ref="northChartRef" class="chart-container" />
      </div>
    </div>

    <!-- Sectors -->
    <div class="section dual-section">
      <div class="card">
        <h2 class="section-title">板块涨幅榜</h2>
        <div class="ranking-list">
          <div v-for="(s, i) in sectors.gainers" :key="s.name" class="ranking-item">
            <span class="rank-num">{{ i + 1 }}</span>
            <span class="rank-name">{{ s.name }}</span>
            <span class="rank-val" :class="s.change_pct >= 0 ? 'up' : 'down'">
              {{ s.change_pct >= 0 ? '+' : '' }}{{ s.change_pct.toFixed(2) }}%
            </span>
          </div>
        </div>
      </div>
      <div class="card">
        <h2 class="section-title">资金流入榜</h2>
        <div class="ranking-list">
          <div v-for="(s, i) in sectors.fund_inflow" :key="s.name" class="ranking-item">
            <span class="rank-num">{{ i + 1 }}</span>
            <span class="rank-name">{{ s.name }}</span>
            <span class="rank-val" :class="s.net_fund_flow >= 0 ? 'up' : 'down'">
              {{ formatFlow(s.net_fund_flow) }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- Positions -->
    <div class="section" v-if="positions.length > 0">
      <h2 class="section-title">持仓监控</h2>
      <div class="positions-grid">
        <div v-for="pos in positions" :key="pos.code" class="card position-card">
          <div class="pos-header">
            <span class="pos-name">{{ pos.stock_name }}</span>
            <span class="pos-code">{{ pos.code }}</span>
          </div>
          <div class="pos-price" :class="pos.change_pct >= 0 ? 'up' : 'down'">
            {{ pos.current_price.toFixed(2) }}
            <span class="pos-pct">{{ pos.change_pct >= 0 ? '+' : '' }}{{ pos.change_pct.toFixed(2) }}%</span>
          </div>
          <div class="pos-pnl" :class="pos.pnl >= 0 ? 'up' : 'down'">
            浮盈: {{ pos.pnl >= 0 ? '+' : '' }}{{ pos.pnl.toFixed(2) }}
            ({{ pos.pnl_pct >= 0 ? '+' : '' }}{{ pos.pnl_pct.toFixed(1) }}%)
          </div>
          <div class="pos-meta">
            买入: {{ pos.buy_price.toFixed(2) }} | {{ pos.shares }}股
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import {
  fetchRealtimeSummary,
  fetchRealtimeNorthFlow,
  fetchRealtimeSectors,
  fetchRealtimePositions,
  type RealtimeSummary,
  type NorthFlowData,
  type SectorData,
  type PositionLive,
} from '@/api/realtime'
import * as echarts from 'echarts'

const summary = ref<RealtimeSummary>({
  indices: [], north_flow: {} as any,
  sectors: { gainers: [], fund_inflow: [] },
  is_trading: false, last_refresh: null,
})
const northFlow = ref<NorthFlowData>({} as any)
const sectors = ref<{ gainers: SectorData[]; fund_inflow: SectorData[] }>({ gainers: [], fund_inflow: [] })
const positions = ref<PositionLive[]>([])
const northChartRef = ref<HTMLElement | null>(null)

let timer: ReturnType<typeof setInterval> | null = null
let chart: echarts.ECharts | null = null

function formatFlow(val: number): string {
  const abs = Math.abs(val)
  const sign = val >= 0 ? '+' : '-'
  if (abs >= 1e8) return `${sign}${(abs / 1e8).toFixed(1)}亿`
  if (abs >= 1e4) return `${sign}${(abs / 1e4).toFixed(0)}万`
  return `${sign}${abs.toFixed(0)}`
}

function formatTime(iso: string): string {
  const d = new Date(iso)
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
}

function renderNorthChart() {
  if (!northChartRef.value || !northFlow.value.timeline?.length) return
  if (!chart) {
    chart = echarts.init(northChartRef.value)
  }
  const tl = northFlow.value.timeline
  chart.setOption({
    grid: { top: 20, right: 20, bottom: 30, left: 60 },
    xAxis: { type: 'category', data: tl.map(t => t.time), axisLabel: { color: '#8b95a5', fontSize: 11 } },
    yAxis: {
      type: 'value',
      axisLabel: {
        color: '#8b95a5', fontSize: 11,
        formatter: (v: number) => `${(v / 1e8).toFixed(0)}亿`,
      },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
    },
    series: [{
      type: 'line', data: tl.map(t => t.net),
      smooth: true, symbol: 'none',
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(239, 68, 68, 0.3)' },
          { offset: 1, color: 'rgba(239, 68, 68, 0.02)' },
        ]),
      },
      lineStyle: { color: '#ef4444', width: 2 },
    }],
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        const p = params[0]
        return `${p.name}<br/>净流入: ${(p.value / 1e8).toFixed(2)}亿`
      },
    },
  })
}

async function refresh() {
  try {
    const [sumRes, northRes, sectorRes, posRes] = await Promise.all([
      fetchRealtimeSummary(),
      fetchRealtimeNorthFlow(),
      fetchRealtimeSectors(),
      fetchRealtimePositions(),
    ])
    summary.value = sumRes.data
    northFlow.value = northRes.data
    sectors.value = sectorRes.data
    positions.value = posRes.data
    await nextTick()
    renderNorthChart()
  } catch {}
}

onMounted(() => {
  refresh()
  timer = setInterval(refresh, 60_000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
  if (chart) { chart.dispose(); chart = null }
})
</script>

<style scoped>
.realtime-page { padding: 0; }
.page-title { font-size: 22px; font-weight: 700; margin-bottom: 4px; }
.page-status { font-size: 13px; color: #22c55e; margin-bottom: 20px; }
.page-status.closed { color: #8b95a5; }
.last-refresh { color: #8b95a5; margin-left: 8px; }

.section { margin-bottom: 24px; }
.section-title { font-size: 16px; font-weight: 600; margin-bottom: 12px; }

.index-section { display: flex; gap: 16px; flex-wrap: wrap; }
.index-card {
  flex: 1; min-width: 180px;
  padding: 16px 20px;
  background: var(--color-surface-elevated, #1a1f2e);
  border-radius: 12px;
}
.idx-name { font-size: 13px; color: #8b95a5; margin-bottom: 6px; }
.idx-price { font-size: 24px; font-weight: 700; }
.idx-change { font-size: 14px; font-weight: 500; margin-top: 4px; }
.idx-amount { font-size: 12px; margin-left: 6px; opacity: 0.7; }

.north-card { padding: 16px 20px; background: var(--color-surface-elevated, #1a1f2e); border-radius: 12px; }
.north-summary { display: flex; gap: 32px; margin-bottom: 16px; flex-wrap: wrap; }
.north-item { display: flex; flex-direction: column; gap: 4px; }
.north-label { font-size: 12px; color: #8b95a5; }
.north-val { font-size: 20px; font-weight: 700; }
.chart-container { width: 100%; height: 240px; }

.dual-section { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.dual-section .card { padding: 16px 20px; background: var(--color-surface-elevated, #1a1f2e); border-radius: 12px; }
.ranking-list { display: flex; flex-direction: column; gap: 8px; }
.ranking-item { display: flex; align-items: center; gap: 10px; padding: 6px 0; border-bottom: 1px solid rgba(255,255,255,0.04); }
.rank-num { width: 20px; font-size: 13px; color: #8b95a5; font-weight: 600; }
.rank-name { flex: 1; font-size: 14px; }
.rank-val { font-size: 14px; font-weight: 500; }

.positions-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 16px; }
.position-card { padding: 16px; background: var(--color-surface-elevated, #1a1f2e); border-radius: 12px; }
.pos-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.pos-name { font-weight: 600; font-size: 15px; }
.pos-code { font-size: 12px; color: #8b95a5; }
.pos-price { font-size: 22px; font-weight: 700; }
.pos-pct { font-size: 14px; margin-left: 6px; }
.pos-pnl { font-size: 14px; margin-top: 6px; }
.pos-meta { font-size: 12px; color: #8b95a5; margin-top: 6px; }

.up { color: #ef4444; }
.down { color: #22c55e; }

.card { background: var(--color-surface-elevated, #1a1f2e); border-radius: 12px; }

@media (max-width: 768px) {
  .dual-section { grid-template-columns: 1fr; }
  .index-section { flex-direction: column; }
}
</style>
```

- [ ] **Step 2: Add route**

Add to `frontend/src/router/index.ts` routes array, after the `/position` route:

```typescript
{ path: '/realtime', name: 'realtime', component: () => import('@/views/RealtimeView.vue') },
```

- [ ] **Step 3: Add sidebar navigation entry**

In `frontend/src/components/layout/AppSidebar.vue`, add a "实时监控" navigation item. Find the existing nav items and add after "持仓管理":

```vue
<router-link to="/realtime" class="nav-item" active-class="active">
  <span class="nav-icon">📊</span>
  <span class="nav-label">实时监控</span>
</router-link>
```

Note: Match the exact structure and class names used by existing nav items in the sidebar. If existing items use a different icon system (e.g., SVG icons or icon components), follow that pattern instead of emoji.

- [ ] **Step 4: Verify in browser**

Start dev server. Click "实时监控" in sidebar. Verify:
- Three index cards render (may show empty data if outside trading hours / no data yet)
- North flow chart renders
- Sector ranking tables render
- Position cards render if positions exist
- Auto-refresh works (wait 60 seconds)
- Mobile responsive layout works at narrow widths

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/RealtimeView.vue frontend/src/router/index.ts frontend/src/components/layout/AppSidebar.vue
git commit -m "feat: add realtime monitoring page with index, north flow, sectors, positions"
```

---

### Task 13: Integration Test + Build Verification

**Files:**
- No new files — verification only

- [ ] **Step 1: Run full backend test suite**

Run: `cd backend && python -m pytest -v`
Expected: All tests PASS

- [ ] **Step 2: Run frontend build**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no errors

- [ ] **Step 3: Run Docker build**

Run: `docker compose build`
Expected: Build succeeds (may need to pull baostock dependency)

- [ ] **Step 4: Verify seed script still works**

Run: `cd backend && python -c "from scripts.seed_demo import seed_demo; print('import OK')"`
Expected: No import errors

- [ ] **Step 5: Final commit + push**

```bash
git push origin master
```

---

### Post-Deployment Steps (Manual)

After pushing to the server:

1. **Server update:**
```bash
cd /opt/quantClaw
git pull
sudo bash start.sh
```

2. **Seed real data (now using EastMoney instead of AKShare):**
```bash
docker exec quantclaw-quantclaw-1 python -m scripts.seed_data
```

3. **Verify in browser:**
- Visit `https://quant.azhefuye.online`
- Check Dashboard — realtime bar should show at top
- Click "实时监控" — full realtime page
- Go to Settings — data source dropdown should show "东方财富"
- During trading hours, data auto-refreshes every 60 seconds
