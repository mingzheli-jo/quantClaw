# P4 Design Spec: AI 智能分析

> Date: 2026-05-27
> Status: Approved
> Scope: LLM-powered stock analysis reports, integrated into daily workflow and web UI

## 1. Problem Statement

QuantClaw generates buy signals with numeric scores and brief reason text, but a quantitative beginner cannot interpret "技术面: MA5 上穿 MA20, MACD 金叉" into actionable trading decisions. The system needs to translate scoring signals into plain-language analysis with risk warnings and operation suggestions.

## 2. Goals

- Generate human-readable AI analysis for recommended stocks, positions, and watchlist
- Support on-demand analysis for any stock via detail page
- Keep cost under 50 RMB/month (target: <5 RMB/month)
- Deliver via: independent "AI 洞察" page, stock detail page button, Feishu post-market summary

## 3. Architecture

```
job_post_market_analyze (existing, 15:30)
        ↓ completes
job_ai_analysis (new, 15:40)
        ↓
┌──────────────────┐
│  ContextBuilder   │  Collects per-stock data:
│  - latest scores  │  scores, kline 5d, sector, north flow,
│  - kline data     │  market sentiment, position info
│  - market context │
└────────┬─────────┘
         ↓
┌──────────────────┐
│  LLMClient        │  Unified interface:
│  - DeepSeek (default) │  send_chat(messages) → str
│  - Qwen (alt)     │  Configurable via SystemConfig
│  - Claude (alt)   │
└────────┬─────────┘
         ↓
┌──────────────────┐
│  AIAnalysis model │  Persisted to database
│  - code, trade_date │
│  - summary (推荐理由) │
│  - risk (风险提示)    │
│  - suggestion (操作建议) │
│  - market_comment     │
│  - raw_response       │
└──────────────────┘
         ↓
    ┌────┴────┐
    ↓         ↓
 Frontend   Feishu
 AI洞察页    盘后报告附带摘要
```

## 4. LLM Client

### Interface

```python
class LLMClient:
    def chat(self, messages: list[dict], temperature: float = 0.3) -> str
```

### Provider: DeepSeek V3 (default)

- API: `https://api.deepseek.com/chat/completions`
- Model: `deepseek-chat`
- Auth: API key via env `DEEPSEEK_API_KEY`
- Cost: ~1 RMB/M input tokens, ~2 RMB/M output tokens

### Provider switching

- Store active provider name in `SystemConfig` table (key: `llm_provider`)
- Default: `deepseek`
- Settings page can switch to `qwen` or `claude`
- Each provider implements the same `chat()` interface

### Configuration

New env vars:
- `DEEPSEEK_API_KEY` — DeepSeek API key
- `QWEN_API_KEY` — Qwen API key (optional)
- `LLM_PROVIDER` — default provider name (fallback to SystemConfig)

## 5. Context Builder

For each stock, assemble a structured context dict:

```python
{
    "code": "000001",
    "name": "平安银行",
    "industry": "银行",
    "scores": {
        "total": 72, "tech": 28, "fund": 22, "momentum": 14, "sentiment": 8
    },
    "reason": "MA5上穿MA20, MACD金叉, 量比1.8",
    "kline_5d": [
        {"date": "2026-05-23", "close": 12.5, "change_pct": 1.2, "volume": 500000},
        ...
    ],
    "market": {
        "up_count": 2800, "down_count": 1500, "limit_up": 45, "limit_down": 8,
        "north_net": 5000000000
    },
    "sector_change_pct": 2.3,
    "position": null | {"buy_price": 12.0, "hold_days": 3, "pnl_pct": 4.2}
}
```

## 6. Prompt Design

System prompt (fixed):

```
你是 QuantClaw 量化信号系统的 AI 分析师。用户是量化小白，需要你用通俗易懂的语言解释股票信号。

分析要求：
1. 推荐理由：用人话解释技术指标的含义，说明为什么系统推荐这只股
2. 风险提示：指出 2-3 个潜在风险（技术面见顶信号、板块轮动、大盘环境等）
3. 操作建议：给出明确建议（积极买入/等回调/观望/建议减仓），并说明理由
4. 市场环境：一句话总结今天大盘对这只股票的影响

语言风格：简洁直白，不用专业术语堆砌，像一个经验丰富的朋友在微信上给你建议。
每段不超过 3 句话。总字数控制在 200-300 字。
```

User prompt (per stock): inject the context JSON.

## 7. Data Model

```python
class AIAnalysis(Base):
    __tablename__ = "ai_analysis"

    id: int (PK)
    code: str(10)         # stock code
    trade_date: date      # analysis date
    summary: str (Text)   # 推荐理由解读
    risk: str (Text)      # 风险提示
    suggestion: str (Text)# 操作建议
    market_comment: str (Text) # 市场环境
    llm_provider: str(20) # which model generated this
    created_at: datetime
    UniqueConstraint("code", "trade_date")
```

## 8. API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/ai/daily` | Today's all AI analyses (for AI洞察 page) |
| GET | `/api/ai/{code}` | Latest AI analysis for a stock |
| POST | `/api/ai/generate/{code}` | On-demand: generate analysis for any stock |

### GET /api/ai/daily

Returns list of today's analyses with stock name, score, and AI text.

### POST /api/ai/generate/{code}

- Builds context for the stock
- Calls LLM
- Saves to `ai_analysis` table
- Returns the analysis
- Rate limit: max 20 calls per day per user (prevent abuse)

## 9. Scheduler Integration

New job `job_ai_analysis` at 15:40 (after signals are generated):

1. Query today's top 3 signals
2. Query active positions
3. Query user's watchlist
4. Deduplicate codes
5. For each code: build context → call LLM → save AIAnalysis
6. Log to SchedulerLog
7. Append AI summaries to Feishu post-market card (or send separate card)

## 10. Frontend: AI 洞察页面

Route: `/ai` — Sidebar entry: "AI 洞察"

**Layout:**
- Top: 市场总览 AI 摘要卡片（大盘分析）
- Below: 股票卡片列表，每张卡片包含：
  - 股票名 + 代码 + 评分
  - AI 分析 4 段文字（推荐理由、风险、建议、市场）
  - 标签：TOP信号 / 持仓 / 自选
  - 点击跳转个股详情

## 11. Frontend: 个股详情页集成

- 在评分雷达下方新增 "AI 分析" 卡片
- 如果有当天的 AIAnalysis 记录，直接展示
- 如果没有，显示"生成 AI 分析"按钮，点击调用 POST /api/ai/generate/{code}
- 生成中显示 loading 状态，完成后展示结果

## 12. Feishu 集成

在盘后报告的每个 TOP 信号下方，附加一行 AI 摘要（只取 summary 的前 50 字）：

```
🤖 AI: 放量突破20日平台，北向连续流入，但板块已涨3天注意回调风险
```

## 13. Cost Control

- Daily auto: ~10 stocks × ~2800 tokens = 28,000 tokens/day
- Monthly auto: 28K × 22 days = 616K tokens ≈ 1-2 RMB
- On-demand: 20 cap/day × 2800 tokens = 56K tokens/day max
- Monthly worst case: (616K + 56K × 22) = 1.85M tokens ≈ 3-4 RMB
- Well under 50 RMB budget

## 14. Error Handling

- LLM API failure: retry 2 times, then skip and log warning
- Rate limit hit: return cached analysis if available, else "暂时无法生成"
- API key missing: disable AI features gracefully, show "未配置 AI 服务" in UI
- Malformed LLM response: use raw text as summary, leave other fields empty

## 15. New Files

### Backend
- `backend/app/services/ai/__init__.py`
- `backend/app/services/ai/llm_client.py` — unified LLM interface
- `backend/app/services/ai/prompts.py` — prompt templates
- `backend/app/services/ai/analyzer.py` — context builder + orchestrator
- `backend/app/models/ai.py` — AIAnalysis model
- `backend/app/api/ai.py` — AI endpoints

### Frontend
- `frontend/src/api/ai.ts` — AI API client
- `frontend/src/views/AIInsightView.vue` — AI 洞察页面

### Modified
- `backend/app/scheduler/jobs.py` — add job_ai_analysis
- `backend/app/scheduler/setup.py` — register new job
- `backend/app/api/__init__.py` — register AI router
- `backend/app/models/__init__.py` — register AIAnalysis
- `backend/app/config.py` — add DEEPSEEK_API_KEY
- `backend/app/services/notify/messages.py` — append AI summary to card
- `frontend/src/views/StockDetailView.vue` — add AI analysis card
- `frontend/src/router/index.ts` — add /ai route
- `frontend/src/components/layout/AppSidebar.vue` — add nav entry

## 16. Out of Scope

- News/announcement scraping (would need separate data source)
- Real-time intraday AI alerts (too costly)
- Fine-tuning models (unnecessary for this use case)
- Multi-turn conversation with AI about stocks
