# P2: 策略插件化 + 回测系统

## 概述

将当前硬编码的量化策略改为可配置的策略模板系统，支持用户创建、复制、修改策略参数。新增回测引擎，能对任意策略在历史数据上模拟交易，输出收益指标、收益曲线和每笔交易明细。

---

## 一、策略模板系统

### 数据模型

新增 `StrategyTemplate` 模型：

```
StrategyTemplate
├── id: int (PK, auto)
├── name: str (策略名称，如"稳健短线"、"均线突破")
├── description: str (策略说明)
├── filter_config: JSON {
│     min_amount_20d: int,    # 最低20日均成交额
│     max_price: float,       # 最高价格
│     min_list_days: int,     # 最低上市天数
│     exclude_bj: bool,       # 排除北交所
│   }
├── score_config: JSON {
│     tech_weight: float,     # 技术面权重 (0-1)
│     fund_weight: float,     # 资金面权重 (0-1)
│     momentum_weight: float, # 动量权重 (0-1)
│     sentiment_weight: float,# 情绪权重 (0-1)
│     ma_periods: [5,10,20],  # 均线周期组合
│     macd_enabled: bool,     # 是否启用 MACD
│     kdj_enabled: bool,      # 是否启用 KDJ
│     bollinger_enabled: bool,# 是否启用布林带
│     volume_ratio_threshold: float, # 量比阈值
│   }
├── signal_config: JSON {
│     min_score: int,         # 最低信号分数
│     top_n: int,             # 每日最多推送数
│     concentration_control: bool, # 是否行业分散
│   }
├── risk_config: JSON {
│     stop_loss_pct: float,   # 止损百分比 (负数, 如 -0.05)
│     take_profit_pct: float, # 止盈百分比 (如 0.12)
│     trailing_trigger: float,# 移动止盈触发 (如 0.07)
│     trailing_drawdown: float,# 移动止盈回撤 (如 0.03)
│     max_hold_days: int,     # 最大持仓天数
│   }
├── is_active: bool (是否用于实盘信号推送，全局仅一个 active)
├── is_builtin: bool (内置策略不可删除)
├── created_at: datetime
├── updated_at: datetime
```

### 内置策略模板

系统预置 4 个策略模板（`is_builtin=True`）：

| 名称 | 特点 | 技/资/动/情权重 |
|------|------|----------------|
| 稳健短线 | 当前默认策略，均衡多因子 | 40/30/20/10 |
| 均线突破 | 重技术面，均线多头+突破 | 60/15/20/5 |
| 资金驱动 | 重资金面，北向+主力流入 | 20/50/15/15 |
| 动量追涨 | 重动量，强势股追涨 | 25/15/50/10 |

"稳健短线"默认 `is_active=True`。

### 策略与调度器集成

`job_post_market_analyze` 现在从数据库读取 `is_active=True` 的策略模板，使用其参数驱动 filter → score → signal 流程，而非硬编码参数。

### 打分引擎重构

现有 `scoring.py` 的 4 个打分函数保持不变，但 `job_post_market_analyze` 中的调用处改为：
- 使用策略模板中的权重来加权各维度分数
- 根据 `score_config` 中的开关控制哪些指标参与计算
- `compute_total_score` 改为接受权重参数：`tech * tech_weight + fund * fund_weight + ...`，归一化到 0-100

### API

```
GET    /api/strategies              → 策略模板列表
POST   /api/strategies              → 创建策略模板
GET    /api/strategies/:id          → 策略详情
PUT    /api/strategies/:id          → 更新策略模板
DELETE /api/strategies/:id          → 删除策略模板 (is_builtin=True 不可删)
PUT    /api/strategies/:id/activate → 设为活跃策略 (其他变为非活跃)
```

### 前端

设置页新增"策略管理"板块：
- 策略卡片列表，显示名称、说明、权重分布、是否激活
- "激活"按钮切换当前使用的策略
- "复制"按钮从已有策略创建新模板
- 编辑弹窗：修改策略名称、各项参数（表单式，分区展示 filter/score/signal/risk）
- 内置策略显示锁定图标，不可删除但可复制

---

## 二、回测引擎

### 回测请求

```
POST /api/backtest/run
Body: {
  strategy_id: int,        # 使用哪个策略模板
  start_date: "2025-09-01",
  end_date: "2026-05-26",
  initial_capital: 50000,  # 初始资金
  benchmark: "000001",     # 基准指数代码 (上证指数)
}
```

回测异步执行。返回 `{ backtest_id: int, status: "running" }`。

### 回测流程

```
For each trading_day in [start_date, end_date]:
  1. 获取当日全市场数据 (从 StockDaily 表读取)
  2. 构建 universe: 读取 StockBasic + 最近 20 日 K 线
  3. 执行策略模板的 hard_filter
  4. 执行策略模板的 score 逻辑
  5. 执行 select_top_n + concentration_control
  6. 模拟买入:
     - 可用资金 / max_positions 平分
     - 以当日收盘价买入
     - 记录交易日志
  7. 检查持仓:
     - 止损: current_price / buy_price - 1 <= stop_loss_pct → 卖出
     - 止盈: current_price / buy_price - 1 >= take_profit_pct → 卖出
     - 最大持仓天数: hold_days >= max_hold_days → 卖出
     - 以当日收盘价卖出
     - 记录交易日志
  8. 计算当日总净值 (现金 + 持仓市值)
  9. 记录当日净值
```

### 数据依赖

回测需要历史 K 线数据。如果数据库中没有足够的历史数据，回测前先自动补充拉取（使用当前活跃的数据源 Provider）。

为避免每次回测都拉数据，拉取过的数据持久化在 StockDaily 表中，下次回测直接复用。

### 回测结果模型

```
BacktestResult
├── id: int (PK, auto)
├── strategy_id: int (FK → StrategyTemplate)
├── strategy_name: str (快照，防止策略被修改后结果失去参考)
├── start_date: date
├── end_date: date
├── initial_capital: float
├── status: str ("running" | "completed" | "failed")
├── error_message: str | null
├── summary: JSON {
│     total_return: float,     # 总收益率 (如 0.12 = 12%)
│     annual_return: float,    # 年化收益率
│     max_drawdown: float,     # 最大回撤 (如 -0.08 = -8%)
│     win_rate: float,         # 胜率 (如 0.65 = 65%)
│     sharpe_ratio: float,     # 夏普比率
│     profit_loss_ratio: float,# 盈亏比
│     total_trades: int,       # 总交易次数
│     benchmark_return: float, # 基准收益率
│   }
├── daily_values: JSON [       # 每日净值序列
│     { "date": "2025-09-01", "value": 50000, "benchmark": 3200.5 },
│     ...
│   ]
├── trades: JSON [             # 每笔交易明细
│     {
│       "code": "600519", "name": "贵州茅台",
│       "buy_date": "2025-09-05", "buy_price": 1650.0,
│       "sell_date": "2025-09-10", "sell_price": 1720.0,
│       "shares": 100, "pnl": 7000.0, "pnl_pct": 4.24,
│       "hold_days": 5, "sell_reason": "take_profit"
│     },
│     ...
│   ]
├── created_at: datetime
```

### 回测 API

```
POST   /api/backtest/run           → 启动回测 (异步)
GET    /api/backtest/:id           → 查询回测状态和结果
GET    /api/backtest/list          → 回测历史列表
DELETE /api/backtest/:id           → 删除回测记录
```

### 回测执行

回测在后台线程执行（使用 Python `threading`），不阻塞 API 请求。前端通过轮询 `GET /api/backtest/:id` 获取进度和结果。

回测过程中更新 `status` 字段，完成后写入 `summary`、`daily_values`、`trades`。

---

## 三、前端

### 策略管理（设置页扩展）

在设置页的"数据源"卡片下方新增"策略管理"区域：

```
┌─────────────────────────────────────────────────────┐
│ 策略管理                               [+ 新建策略]  │
├─────────────────────────────────────────────────────┤
│ ┌─ 稳健短线 ──────────────┐  ┌─ 均线突破 ──────────┐ │
│ │ ★ 当前激活              │  │                    │ │
│ │ 技40 资30 动20 情10     │  │ 技60 资15 动20 情5  │ │
│ │ [编辑] [复制]           │  │ [激活] [编辑] [复制]│ │
│ └────────────────────────┘  └────────────────────┘ │
│ ┌─ 资金驱动 ──────────────┐  ┌─ 动量追涨 ──────────┐ │
│ │                        │  │                    │ │
│ │ 技20 资50 动15 情15     │  │ 技25 资15 动50 情10 │ │
│ │ [激活] [编辑] [复制]    │  │ [激活] [编辑] [复制]│ │
│ └────────────────────────┘  └────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

### 回测页面（新增路由 `/backtest`）

```
┌──────────────────────────────────────────────────────┐
│ 策略回测                                              │
├──────────────────────────────────────────────────────┤
│ 策略: [下拉选择]  开始: [日期]  结束: [日期]          │
│ 初始资金: [50000]                    [开始回测]       │
├──────────────────────────────────────────────────────┤
│                                                      │
│ 结果卡片:                                            │
│ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐         │
│ │总收益率 │ │最大回撤 │ │ 胜率   │ │夏普比率 │         │
│ │+12.3%  │ │-5.2%   │ │ 65%   │ │ 1.85   │         │
│ └────────┘ └────────┘ └────────┘ └────────┘         │
│                                                      │
│ 收益曲线 (ECharts):                                  │
│ ┌──────────────────────────────────────────┐         │
│ │ ─── 策略净值  ─── 基准(上证)             │         │
│ │                          ╱               │         │
│ │              ╱──────────╱                │         │
│ │ ────────────╱                            │         │
│ └──────────────────────────────────────────┘         │
│                                                      │
│ 交易明细:                                            │
│ ┌─────┬──────┬──────┬──────┬──────┬───────┐         │
│ │股票  │买入日 │买入价 │卖出日 │卖出价 │盈亏    │         │
│ ├─────┼──────┼──────┼──────┼──────┼───────┤         │
│ │茅台  │09-05 │1650  │09-10 │1720  │+4.24% │         │
│ │...   │      │      │      │      │       │         │
│ └─────┴──────┴──────┴──────┴──────┴───────┘         │
├──────────────────────────────────────────────────────┤
│ 历史回测记录                                          │
│ [稳健短线 2025-09→2026-05 +12.3%] [均线突破 ...]     │
└──────────────────────────────────────────────────────┘
```

---

## 四、技术要点

### 文件新增/修改清单

**新增：**
- `backend/app/models/strategy.py` — StrategyTemplate, BacktestResult 模型
- `backend/app/api/strategy.py` — 策略 CRUD API
- `backend/app/api/backtest.py` — 回测 API
- `backend/app/schemas/strategy.py` — 策略和回测 schemas
- `backend/app/schemas/backtest.py` — 回测请求/结果 schemas
- `backend/app/services/backtest/engine.py` — 回测引擎核心
- `backend/app/services/backtest/__init__.py`
- `frontend/src/api/strategy.ts` — 策略 API 客户端
- `frontend/src/api/backtest.ts` — 回测 API 客户端
- `frontend/src/views/BacktestView.vue` — 回测页面
- `frontend/src/components/strategy/StrategyCard.vue` — 策略卡片
- `frontend/src/components/strategy/StrategyEditor.vue` — 策略编辑弹窗
- `frontend/src/components/backtest/BacktestResultChart.vue` — 收益曲线图
- `frontend/src/components/backtest/TradeTable.vue` — 交易明细表

**修改：**
- `backend/app/models/__init__.py` — 注册新模型
- `backend/app/api/__init__.py` — 注册新路由
- `backend/app/main.py` — 种子内置策略
- `backend/app/scheduler/jobs.py` — `job_post_market_analyze` 改为读取活跃策略模板
- `backend/app/services/strategy/scoring.py` — `compute_total_score` 支持加权
- `frontend/src/router/index.ts` — 添加 /backtest 路由
- `frontend/src/views/SettingsView.vue` — 集成策略管理
- `frontend/src/components/layout/AppSidebar.vue` — 添加回测导航

### 性能考虑

- 回测涉及大量 DB 查询（每个交易日 × 每只股票），使用批量查询 + 内存缓存
- 回测前一次性加载所需日期范围的全部 K 线数据到内存
- 200 只股票 × 250 个交易日 ≈ 50000 行，pandas 内存处理没问题
- 回测在后台线程运行，不阻塞 API

### 错误处理

- 历史数据不足时，回测前自动补充拉取
- 拉取失败时返回错误提示，不执行回测
- 回测过程中异常写入 `error_message` 字段，状态设为 `failed`

### 测试

- 回测引擎单元测试：用固定 K 线数据验证买卖逻辑、指标计算
- 策略 API 集成测试：CRUD + 激活切换
- 回测 API 集成测试：启动 → 查询状态 → 获取结果
