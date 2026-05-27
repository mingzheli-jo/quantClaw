# P5 Design Spec: Factor Validation (因子有效性检验)

> Date: 2026-05-27
> Status: Approved
> Scope: Validate existing scoring factors with statistical metrics, surface results in frontend, suggest weight adjustments

## 1. Problem Statement

QuantClaw's 4-factor scoring weights (tech 40%, fund 30%, momentum 20%, sentiment 10%) were set by intuition. After accumulating 20+ trading days of signal data, the system should validate which factors actually predict next-day returns, how stable they are, and whether the weights should be adjusted.

## 2. Goals

- Compute IC (Information Coefficient) for each factor daily
- Show factor effectiveness trends over time
- Measure signal decay (T+1 to T+5)
- Generate weight adjustment suggestions (AI-powered via P4 LLM)
- Run automatically once per week; manual trigger available

## 3. Core Metrics

### IC (Information Coefficient)

Cross-sectional Spearman rank correlation between factor scores and next-day returns.

```
IC_t = rank_corr(factor_score_t, return_t+1)
```

Interpretation:
- IC > 0.03: factor has predictive value
- IC > 0.05: factor is strong
- IC < 0: factor is contrarian (or broken)

### IC_IR (Information Ratio)

Stability of IC over a rolling window.

```
IC_IR = mean(IC) / std(IC)
```

- IC_IR > 0.5: factor is reliably useful
- IC_IR < 0.3: factor is noisy

### Factor Return

Split stocks into 5 groups by factor score. Long top group, short bottom group.

```
factor_return_t = mean_return(top_20%) - mean_return(bottom_20%)
```

### Signal Decay

Compute IC at T+1, T+2, ... T+5 to see how quickly the signal loses power.

## 4. Architecture

```
job_factor_validate (Sunday 20:00, weekly)
        ↓
┌──────────────────┐
│  FactorCalculator │  For each trading day in window:
│  - query signals  │  extract per-stock factor scores
│  - query returns  │  compute next-day returns
└────────┬─────────┘
         ↓
┌──────────────────┐
│  FactorValidator  │  Compute:
│  - IC per day     │  - daily IC for each factor
│  - IC_IR          │  - rolling IC_IR
│  - factor return  │  - quintile returns
│  - decay curve    │  - T+1 to T+5 IC
└────────┬─────────┘
         ↓
┌──────────────────┐
│  FactorReport     │  Store results to DB
│  model            │  Generate weight suggestion via LLM (P4)
└──────────────────┘
         ↓
    ┌────┴────┐
    ↓         ↓
 Frontend   Optional:
 因子验证页   Feishu weekly summary
```

## 5. Data Model

### FactorIC (daily IC records)

```python
class FactorIC(Base):
    __tablename__ = "factor_ic"

    id: int (PK)
    trade_date: date
    factor_name: str(20)    # "tech", "fund", "momentum", "sentiment", "total"
    ic_value: float          # Spearman correlation
    stock_count: int         # how many stocks in the cross-section
    created_at: datetime
    UniqueConstraint("trade_date", "factor_name")
```

### FactorReport (weekly summary)

```python
class FactorReport(Base):
    __tablename__ = "factor_report"

    id: int (PK)
    report_date: date        # date the report was generated
    window_days: int         # how many trading days analyzed (e.g., 20)
    results: str (JSON)      # full results: IC means, IR, decay, quintile returns
    weight_suggestion: str (JSON) # suggested weights {"tech": 0.35, "fund": 0.25, ...}
    ai_commentary: str (Text)    # AI explanation of the results (via P4 LLM)
    created_at: datetime
```

## 6. Factor Calculator

For each trading day `t` in the analysis window:

1. Query all `Signal` records for date `t` → extract `tech_score`, `fund_score`, `momentum_score`, `sentiment_score`, `score` (total)
2. Query `StockDaily` for date `t+1` → get `change_pct` as the forward return
3. Join on `code`
4. For each factor: compute Spearman rank correlation between factor score and `change_pct`
5. Store as `FactorIC` record

Minimum requirement: at least 30 stocks with both signal and return data on a given day.

## 7. Factor Validator

Given a window of daily IC values (default: last 20 trading days):

```python
def validate(factor_ics: list[FactorIC], window: int = 20) -> dict:
    return {
        "factor_name": "tech",
        "ic_mean": 0.042,
        "ic_std": 0.038,
        "ic_ir": 1.11,          # ic_mean / ic_std
        "positive_rate": 0.65,  # % of days where IC > 0
        "decay": {
            "T+1": 0.042,
            "T+2": 0.031,
            "T+3": 0.018,
            "T+4": 0.005,
            "T+5": -0.002,
        },
        "quintile_returns": {
            "Q1_top": 0.82,     # mean daily return % of top 20%
            "Q5_bottom": -0.31, # mean daily return % of bottom 20%
            "spread": 1.13,
        },
        "rating": "strong",     # strong / moderate / weak / ineffective
    }
```

Rating rules:
- IC_IR > 0.5 and ic_mean > 0.03 → "strong"
- IC_IR > 0.3 and ic_mean > 0.02 → "moderate"
- IC_IR > 0.1 and ic_mean > 0.01 → "weak"
- else → "ineffective"

## 8. Weight Suggestion

After validation, suggest new weights proportional to IC_IR:

```python
def suggest_weights(results: dict[str, dict]) -> dict[str, float]:
    scores = {name: max(r["ic_ir"], 0) for name, r in results.items() if name != "total"}
    total = sum(scores.values()) or 1
    return {name: round(s / total, 2) for name, s in scores.items()}
```

If P4 LLM is available, also generate AI commentary explaining the results:
- Which factors improved/declined
- What the weight change means for the strategy
- Whether the user should apply the new weights

## 9. API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/factor/latest` | Latest factor report with IC chart data |
| GET | `/api/factor/ic-history` | Daily IC values for all factors (for chart) |
| POST | `/api/factor/run` | Manually trigger factor validation |

### GET /api/factor/latest

Returns latest `FactorReport` with parsed results + AI commentary.

### GET /api/factor/ic-history

Query params: `days` (default 60)
Returns daily IC values per factor for charting.

### POST /api/factor/run

Triggers validation for the last N trading days. Returns the generated report.
Only callable once per day (rate limit).

## 10. Scheduler

New job `job_factor_validate`:
- Schedule: Sunday 20:00 (weekly)
- Window: last 20 trading days
- Steps:
  1. Calculate IC for any new trading days not yet in `factor_ic`
  2. Run validation over the window
  3. Generate weight suggestion
  4. If P4 LLM available, generate AI commentary
  5. Save `FactorReport`
  6. Log to SchedulerLog

## 11. Frontend: 因子验证页面

Route: `/factor` — Sidebar entry: "因子验证"

**Layout:**

### Top: Summary Cards (4)
One per factor, showing: factor name, IC_IR, rating (color-coded badge), current weight vs suggested weight.

### Middle: IC Trend Chart (ECharts)
- X-axis: trading dates
- Y-axis: IC value
- 4 lines (one per factor), color-coded
- Zero line highlighted
- Tooltip shows exact values

### Middle: Decay Curve Chart
- X-axis: T+1 to T+5
- Y-axis: IC value
- 4 lines showing how each factor's signal decays

### Bottom: Detail Table
| Factor | IC Mean | IC Std | IC_IR | Positive Rate | Rating | Current Weight | Suggested |
|--------|---------|--------|-------|---------------|--------|---------------|-----------|

### Weight Suggestion Card
- Show current vs suggested weights
- AI commentary explaining why
- "应用建议权重" button (updates active strategy template's score_config)

## 12. Data Requirement

- Minimum: 20 trading days of signal data (~1 calendar month)
- Until enough data: show "数据积累中，需要至少20个交易日" message
- Count available days on page load and show progress bar

## 13. New Files

### Backend
- `backend/app/services/factor/__init__.py`
- `backend/app/services/factor/calculator.py` — daily IC calculation
- `backend/app/services/factor/validator.py` — IC_IR, decay, quintile, rating
- `backend/app/services/factor/report.py` — weight suggestion + AI commentary
- `backend/app/models/factor.py` — FactorIC, FactorReport models
- `backend/app/api/factor.py` — factor endpoints

### Frontend
- `frontend/src/api/factor.ts` — factor API client
- `frontend/src/views/FactorView.vue` — 因子验证页面

### Modified
- `backend/app/scheduler/jobs.py` — add job_factor_validate
- `backend/app/scheduler/setup.py` — register weekly job
- `backend/app/api/__init__.py` — register factor router
- `backend/app/models/__init__.py` — register models
- `frontend/src/router/index.ts` — add /factor route
- `frontend/src/components/layout/AppSidebar.vue` — add nav entry

## 14. Out of Scope

- Custom user-defined factors (future P6)
- Multi-factor portfolio optimization (Markowitz etc.)
- Factor neutralization (sector/size)
- Intraday factor analysis
- Automatic weight application without user confirmation
