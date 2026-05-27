# P3 Design Spec: Data Stability + Trading Experience

> Date: 2026-05-27
> Status: Draft
> Scope: Data source resilience, collection monitoring, UX improvements (watchlist, comparison, mobile, notifications)

## 1. Problem Statement

QuantClaw P0-P2 core is feature-complete but has three production gaps:

1. **Data fragility**: EastMoney IP bans disrupt daily collection; BaoStock lacks north flow/sector/sentiment data; no automatic failover between sources.
2. **No observability**: Scheduler jobs run silently; failures are invisible until the user notices missing data.
3. **UX friction**: No watchlist, no stock comparison, no mobile layout, notification messages lack actionable detail.

## 2. Architecture Overview

### Batch 1: Data Stability

```
                          +-----------------+
                          | SmartFetcher    |
                          | (auto-failover) |
                          +--------+--------+
                                   |
                    +--------------+--------------+
                    |                             |
             +------+------+              +------+------+
             | EastMoney   |              | BaoStock    |
             | (primary)   |              | (fallback)  |
             +------+------+              +------+------+
                    |                             |
                    +-------- Hybrid Mode --------+
                    | Stocks+Klines: BaoStock     |
                    | NorthFlow/Sector: EastMoney |
                    +-----------------------------+

             +------------------+
             | CollectionMonitor|
             | - success/fail   |
             | - record counts  |
             | - Feishu alert   |
             +------------------+

             +------------------+
             | System Health    |
             | Page (frontend)  |
             +------------------+
```

### Batch 2: UX Improvements

```
  +-------------+    +----------------+    +-----------------+
  | Watchlist    |    | StockCompare   |    | Mobile Layout   |
  | - CRUD API  |    | - 2-4 stocks   |    | - Bottom TabBar |
  | - Favorites |    | - Radar overlay|    | - Responsive    |
  | - Page      |    | - KLine stack  |    | - Touch-first   |
  +-------------+    +----------------+    +-----------------+

  +---------------------+
  | Enhanced Feishu Msgs |
  | - Key metric deltas  |
  | - Stop-loss warnings |
  | - Deep link to web   |
  +---------------------+
```

## 3. Batch 1: Data Stability

### 3.1 Smart Data Source Failover

**Goal**: Automatic failover from EastMoney to BaoStock when requests fail, with hybrid mode for data types BaoStock doesn't support.

**Implementation**:

- Add `SmartFetcher` wrapper around `DataSourceManager`
- For each fetch call: try primary source first, on failure (3 retries exhausted) switch to fallback
- North flow, sector, sentiment: always attempt EastMoney first (single request, low ban risk), skip silently if failed
- Add anti-ban measures to EastMoney provider:
  - Random delay between requests: 0.3-0.8s (was fixed 0.3s)
  - Rotate 5+ User-Agent strings
  - Add random `Referer` variation
  - If response returns <1000 stocks, mark source as degraded for 1 hour

**Data source decision matrix**:

| Data Type | Primary | Fallback | On Both Fail |
|-----------|---------|----------|-------------|
| Stock list | EastMoney | BaoStock | Use cached |
| K-lines | EastMoney | BaoStock | Skip today |
| North flow | EastMoney | N/A | Skip (optional data) |
| Sector | EastMoney | N/A | Skip (optional data) |
| Sentiment | EastMoney | BaoStock (calc from stock list) | Skip |

**New files**:
- `backend/app/services/data/smart_fetcher.py`

**Modified files**:
- `backend/app/services/data/providers/eastmoney.py` (anti-ban enhancements)
- `backend/app/scheduler/jobs.py` (use SmartFetcher)
- `backend/scripts/seed_data.py` (use SmartFetcher)

### 3.2 Collection Monitoring & Alerting

**Goal**: Know whether daily data collection succeeded, how much data was collected, and get alerted on failures.

**Implementation**:

Extend existing `SchedulerLog` model:

```python
class SchedulerLog(Base):
    __tablename__ = "scheduler_log"
    id: int (PK)
    job_name: str           # "post_market_collect", "post_market_analyze", etc.
    run_date: date
    started_at: datetime
    finished_at: datetime | None
    status: str             # "success" | "partial" | "failed"
    records_collected: int  # total rows inserted/updated
    details: str            # JSON: per-source breakdown, errors
    error_message: str | None
```

After each scheduler job completes:
- Write a `SchedulerLog` entry with counts and status
- If status is "failed" or "partial": send Feishu alert with details
- "partial" means: some data types succeeded but others failed (e.g., klines OK but north flow failed)

**New API endpoints**:
- `GET /api/system/health` — last 7 days of scheduler logs, data freshness check
- `GET /api/system/health/summary` — quick status: last successful run, any failures today

**New frontend page**:
- System Health page at `/system` route
- Table: job name, date, status (color-coded), records, duration
- Status cards at top: "Last collection: 2h ago", "Today's data: Complete/Partial/Missing"

### 3.3 BaoStock Data Supplement

**Goal**: When using BaoStock as primary, supplement missing data types via EastMoney lightweight requests.

Already partially implemented in `seed_data.py` (hybrid mode). Needs to be extended to the daily scheduler jobs:

- In `job_post_market_collect`: after BaoStock kline collection, call EastMoney for north flow + sector + sentiment
- These are 3 HTTP requests total, well below any rate-limit threshold
- If EastMoney is also blocked for these, skip gracefully (data is enrichment, not critical)

**Market sentiment from BaoStock**:
- BaoStock stock list includes `tradeStatus` field
- Count up/down/flat from stock list change_pct to derive limit_up, limit_down, up_count, down_count
- Implement as `BaostockProvider.fetch_market_sentiment()` using existing stock list data

## 4. Batch 2: Trading Experience

### 4.1 Watchlist (Self-selected Stocks)

**Data model**:

```python
class Watchlist(Base):
    __tablename__ = "watchlist"
    id: int (PK)
    user_id: int (FK -> user.id)
    code: str(10)
    added_at: datetime
    note: str | None        # optional user note
    UniqueConstraint("user_id", "code")
```

**API endpoints**:
- `GET /api/watchlist` — list user's watchlist with latest score/price
- `POST /api/watchlist` — add stock `{ code: "000001" }`
- `DELETE /api/watchlist/{code}` — remove stock
- `GET /api/watchlist/signals` — today's signals for watchlisted stocks only

**Frontend**:
- New sidebar entry: "自选股" between "选股扫描" and "持仓管理"
- Watchlist page: table with code, name, latest price, score, change_pct, actions
- Add-to-watchlist button on: search results dropdown, stock detail page, scan ranking table
- Heart/star icon toggle for add/remove

**Feishu integration**:
- In post-market Feishu message, add a "自选股动态" section
- Highlight watchlisted stocks that appear in today's signals

### 4.2 Stock Comparison

**Goal**: Compare 2-4 stocks side-by-side on scores, indicators, and price trends.

**API endpoint**:
- `GET /api/stock/compare?codes=000001,600036,601318` — returns scores + recent klines for all requested codes

**Frontend**:
- New page at `/compare` route, sidebar entry: "个股对比"
- Stock picker: use the search component to add stocks (max 4)
- Comparison views:
  - Radar chart overlay (all stocks on one radar)
  - Score breakdown table (side-by-side columns)
  - K-line overlay chart (normalized to percentage change from first day)
  - Key metrics row: price, change_pct, volume_ratio, PE (if available)

**Entry points**:
- "对比" button on stock detail page
- Multi-select on scan ranking table → "对比选中"
- Direct from sidebar navigation

### 4.3 Mobile Responsive Layout

**Goal**: Dashboard, watchlist, and position pages usable on mobile. Not pixel-perfect, just functional.

**Approach**: CSS-only responsive, no separate mobile app or components.

**Breakpoints**:
- `>= 1024px`: Current desktop layout (sidebar + content)
- `768px - 1023px`: Collapsed sidebar (icons only) + full content
- `< 768px`: No sidebar, bottom Tab Bar navigation (5 tabs: Dashboard, Scan, Watchlist, Position, More)

**Changes**:
- `AppLayout.vue`: Media queries for layout switch
- `AppSidebar.vue`: Hide on mobile, show bottom TabBar component instead
- `AppHeader.vue`: Responsive search (collapse to icon on mobile, expand on tap)
- Dashboard cards: Stack vertically on mobile, full-width
- Tables: Horizontal scroll on narrow screens
- Charts: Reduce height, touch-friendly tooltips

**Priority pages for mobile** (must work well):
1. Dashboard (signals overview)
2. Watchlist (quick check)
3. Position (stop-loss alerts)
4. Stock detail (K-line + score)

**Skip for mobile** (desktop-only is fine):
- Backtest (complex parameters)
- Settings (infrequent use)
- System health (admin)

### 4.4 Enhanced Feishu Notifications

**Goal**: More actionable messages with key metric changes and deep links.

**Improvements to post-market message**:
- Add "关键变化" section: volume ratio spikes (>2x), north flow direction change, sector rotation
- For each TOP signal: show delta vs yesterday's score (e.g., "+12 points, 技术面突破")
- Add clickable link to web dashboard: `https://quant.azhefuye.online/stock/{code}`

**New intraday alert triggers**:
- Watchlisted stock hits intraday signal threshold
- Position approaching stop-loss within 2% buffer
- Market-wide sentiment shift (e.g., limit-down count > 50)

**Message format upgrade**:
- Use Feishu interactive card v2 with collapsible sections
- Critical alerts (stop-loss proximity) use red header
- Normal signals use green/neutral header

## 5. Data Model Changes Summary

| Table | Change | Details |
|-------|--------|---------|
| `scheduler_log` | Extend | Add `records_collected`, `details`, `error_message` columns |
| `watchlist` | New | User watchlist with notes |
| `system_config` | No change | Already supports data source config |

## 6. New Routes Summary

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/system/health` | Scheduler logs (7 days) |
| GET | `/api/system/health/summary` | Quick health status |
| GET | `/api/watchlist` | User's watchlist |
| POST | `/api/watchlist` | Add to watchlist |
| DELETE | `/api/watchlist/{code}` | Remove from watchlist |
| GET | `/api/watchlist/signals` | Signals for watchlisted stocks |
| GET | `/api/stock/compare` | Multi-stock comparison data |

## 7. New Frontend Pages

| Route | Page | Sidebar Label |
|-------|------|---------------|
| `/watchlist` | WatchlistView | 自选股 |
| `/compare` | CompareView | 个股对比 |
| `/system` | SystemHealthView | 系统健康 (in Settings submenu) |

## 8. Implementation Order

**Batch 1 (Data Stability)** — Do first, ~10 tasks:
1. SmartFetcher with auto-failover
2. EastMoney anti-ban enhancements
3. BaoStock sentiment calculation
4. SchedulerLog extension
5. Collection monitoring API
6. System health frontend page
7. Scheduler jobs integration
8. Feishu failure alerts
9. seed_data.py update to use SmartFetcher
10. End-to-end test: simulate EastMoney failure → verify failover

**Batch 2 (UX)** — After data is stable, ~12 tasks:
1. Watchlist model + API
2. Watchlist frontend page
3. Add-to-watchlist buttons across pages
4. Stock compare API
5. Compare frontend page (radar + kline overlay)
6. Mobile responsive: layout breakpoints + TabBar
7. Mobile responsive: Dashboard + Watchlist pages
8. Mobile responsive: Position + Stock detail pages
9. Enhanced Feishu post-market message
10. New Feishu intraday alert triggers
11. Feishu deep links to web
12. Watchlist signals in Feishu daily message

## 9. Out of Scope

- Native mobile app (web responsive is sufficient)
- Real-time WebSocket push (polling + Feishu is enough)
- Multi-user support (single user system)
- Third data source integration (two sources is enough for now)
- AI/LLM analysis (deferred to P4)
