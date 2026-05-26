# P0+P1: 数据源双源切换 + 实时行情监控

## 概述

解决两个问题：(1) AKShare 在腾讯云服务器无法连接，替换为东方财富 HTTP 直调 + BaoStock 双数据源，页面可切换；(2) 交易时段每分钟更新大盘指数、资金流向、板块轮动、持仓股实时数据。

## P0: 数据源双源切换

### 架构

引入 Provider 适配器模式，所有数据获取经过统一接口，底层可切换实现。

```
SystemConfig (DB: data_source = "eastmoney" | "baostock")
    ↓
DataSourceManager.get_provider() → AbstractProvider
    ├── EastmoneyProvider  ← 默认，HTTP 直调，无第三方依赖
    └── BaostockProvider   ← 备选，BaoStock SDK
    ↓
fetcher.py (5 个函数接口不变，内部委托给 Provider)
```

### AbstractProvider 接口

所有 Provider 实现以下方法，返回格式与现有 fetcher 一致：

| 方法 | 返回 | 说明 |
|------|------|------|
| `fetch_stock_basic_list()` | DataFrame | 全市场股票列表 |
| `fetch_daily_klines(code, start, end)` | DataFrame | 单只股票日 K |
| `fetch_north_flow(days)` | DataFrame | 北向资金流水 |
| `fetch_sector_daily()` | DataFrame | 行业板块日数据 |
| `fetch_market_sentiment()` | dict | 市场情绪指标 |

### EastmoneyProvider

直接 HTTP 请求东方财富公开 API（`push2his.eastmoney.com`、`push2.eastmoney.com` 等），不依赖 AKShare。

关键端点：
- 股票列表 + 实时行情：`http://push2.eastmoney.com/api/qt/clist/get` (fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23)
- 日 K 线：`http://push2his.eastmoney.com/api/qt/stock/kline/get`
- 北向资金：`http://push2.eastmoney.com/api/qt/kamtbs.wss/get`（或 `http://push2his.eastmoney.com/api/qt/kamt.kline/get`）
- 板块数据：`http://push2.eastmoney.com/api/qt/clist/get` (fs=m:90)
- 市场情绪：从股票列表实时行情数据聚合计算

实现要点：
- 使用 `httpx`（已在 requirements.txt）发请求
- 设置合理的 User-Agent 和 Referer 头
- 超时 10 秒，重试 3 次
- 解析东方财富 JSON 响应格式（`data.diff` 数组）

### BaostockProvider

使用 `baostock` SDK（需新增依赖）。

能力矩阵：

| 功能 | BaoStock 支持 | 说明 |
|------|:---:|------|
| 股票列表 | Y | `bs.query_stock_basic()` |
| 日 K 线 | Y | `bs.query_history_k_data_plus()` |
| 北向资金 | N | BaoStock 不提供，返回空 DataFrame |
| 板块数据 | N | 不提供，返回空 DataFrame |
| 市场情绪 | N | 不提供，返回空 dict |

BaoStock 作为备选源，主要用于历史 K 线数据。北向资金和板块数据在 BaoStock 模式下不可用，前端对应模块显示"数据源不支持"提示。

### 数据源配置

**后端**：新增 `SystemConfig` 模型（或复用已有配置表）。

```python
class SystemConfig(Base):
    __tablename__ = "system_config"
    key = Column(String, primary_key=True)
    value = Column(String, nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
```

初始记录：`key="data_source", value="eastmoney"`

**API**：
- `GET /api/settings/data-source` → `{"source": "eastmoney"}`
- `PUT /api/settings/data-source` → `{"source": "baostock"}` → 200

切换后 `DataSourceManager` 重新加载 Provider，下次调度任务或手动触发时使用新源。

**前端**：设置页新增"数据源"下拉选择卡片，选项：东方财富 / BaoStock。

### 交易日历

当前 `trading_calendar.py` 依赖 AKShare 的 `ak.tool_trade_date_hist_sina()`。改为：
- 优先用东方财富 API 获取交易日历
- 回退：内置 2026 年交易日列表（周末 + 法定节假日排除）
- 不再依赖 AKShare

### 影响范围

- `backend/app/services/data/fetcher.py` — 内部实现改为委托给 Provider
- `backend/app/scheduler/trading_calendar.py` — 去掉 AKShare 依赖
- `backend/app/services/data/maintenance.py` — 无需改（调用 fetcher 接口不变）
- `backend/app/scheduler/jobs.py` — 无需改（调用 fetcher 接口不变）
- `backend/scripts/seed_data.py` — 无需改（调用 fetcher 接口不变）
- `backend/requirements.txt` — 移除 `akshare`，新增 `baostock`
- 前端设置页 — 新增数据源选择

### seed_data 脚本

seed 脚本调用的是 `fetcher.py` 的公共接口，数据源切换后 seed 脚本自动使用新源，无需修改。部署后在页面设置数据源，然后 `docker exec quantclaw-quantclaw-1 python -m scripts.seed_data` 即可灌入真实数据。

---

## P1: 实时行情监控

### 后端

#### RealtimeService

新增 `backend/app/services/data/realtime.py`，负责实时数据采集和缓存。

数据项：

| 数据 | 刷新间隔 | 数据源 | 缓存方式 |
|------|---------|--------|---------|
| 三大指数（上证/深证/创业板）实时价格 + 分时数据 | 60s | 东方财富 HTTP | 内存 dict |
| 北向资金实时累计净流入 | 60s | 东方财富 HTTP | 内存 dict |
| 行业板块涨跌 TOP10 + 资金流入 TOP10 | 60s | 东方财富 HTTP | 内存 dict |
| 持仓股实时价格 + 涨跌幅 | 60s | 东方财富 HTTP | 内存 dict |

实时数据不写数据库，仅缓存在内存。服务重启后下次采集时恢复。

注意：实时行情固定使用东方财富 HTTP（BaoStock 不支持实时数据），不受数据源设置影响。

#### 调度

使用 APScheduler `IntervalTrigger(seconds=60)` 调度实时采集任务。

交易时段判断：
- 9:15-11:35, 12:55-15:05（含集合竞价前后缓冲）
- 非交易时段自动暂停采集
- 非交易日不启动

#### API 端点

```
GET /api/realtime/indices       → 三大指数实时数据 + 分时序列
GET /api/realtime/north-flow    → 北向资金实时累计数据
GET /api/realtime/sectors       → 板块涨跌排行 + 资金流入排行
GET /api/realtime/positions     → 持仓股实时价格和盈亏
GET /api/realtime/summary       → 聚合接口（以上所有数据一次返回）
```

`/summary` 用于总览页精简条，减少前端请求次数。

#### 东方财富实时 API

| 数据 | 端点 |
|------|------|
| 指数实时 | `http://push2.eastmoney.com/api/qt/ulist.np/get` (secids=1.000001,0.399001,0.399006) |
| 指数分时 | `http://push2.eastmoney.com/api/qt/stock/trends2/get` |
| 北向实时 | `http://push2.eastmoney.com/api/qt/kamt.rtmin/get` |
| 板块排行 | `http://push2.eastmoney.com/api/qt/clist/get` (fs=m:90, fid=f3, po=1) |
| 个股实时 | `http://push2.eastmoney.com/api/qt/ulist.np/get` (secids=具体持仓股代码) |

### 前端

#### 总览页实时指标条

在现有总览页（Dashboard）顶部新增一行实时数据条：

```
┌─────────────────────────────────────────────────────────────────┐
│ 上证 3285.62 ▲+0.83%  深证 10521.3 ▲+1.12%  创业板 2103.5 ▲+1.45% │
│ 北向净流入 +42.3亿    涨:2856 跌:1923 平:312                      │
└─────────────────────────────────────────────────────────────────┘
```

- 每 60 秒自动刷新（调用 `/api/realtime/summary`）
- 涨绿跌红配色
- 非交易时段显示上一交易日收盘数据，标注"已收盘"

#### 新增「实时监控」页面

导航栏新增"实时监控"入口，页面布局：

```
┌────────────────────────────────────────────────────┐
│  指数分时图（上证/深证/创业板 切换）                    │
│  [TradingView Lightweight Charts 分时曲线]           │
├────────────────────┬───────────────────────────────┤
│ 北向资金累计曲线     │  持仓股实时监控                  │
│ [ECharts 面积图]    │  ┌──────────────────────────┐  │
│                    │  │ 贵州茅台  1856.20 ▲+2.3%  │  │
│                    │  │ 浮盈: +856.00 (+4.8%)     │  │
│                    │  ├──────────────────────────┤  │
│                    │  │ 招商银行  35.62  ▼-0.5%   │  │
│                    │  │ 浮亏: -120.00 (-3.2%)     │  │
│                    │  └──────────────────────────┘  │
├────────────────────┴───────────────────────────────┤
│ 板块涨跌排行                    资金流入排行          │
│ 1. 半导体 +4.2%               1. 白酒 +12.3亿      │
│ 2. 新能源 +3.1%               2. 银行 +8.7亿       │
│ 3. AI    +2.8%               3. 半导体 +6.2亿      │
│ ...                           ...                  │
└────────────────────────────────────────────────────┘
```

- 所有数据 60 秒自动刷新
- 指数分时图使用 TradingView Lightweight Charts（项目已引入）
- 北向资金和板块排行使用 ECharts（项目已引入）
- 持仓股卡片实时更新价格和浮盈浮亏
- 非交易时段显示收盘数据 + 灰色"已收盘"标签

### 路由

前端新增路由：`/realtime` → RealtimeMonitor.vue

---

## 技术要点

### 依赖变更

```
移除: akshare
新增: baostock
保留: httpx (已有)
```

### 文件新增/修改清单

**新增文件：**
- `backend/app/services/data/providers/__init__.py`
- `backend/app/services/data/providers/base.py` — AbstractProvider
- `backend/app/services/data/providers/eastmoney.py` — 东方财富 HTTP
- `backend/app/services/data/providers/baostock_provider.py` — BaoStock SDK
- `backend/app/services/data/realtime.py` — 实时数据采集服务
- `backend/app/models/config.py` — SystemConfig 模型
- `backend/app/routers/realtime.py` — 实时数据 API
- `backend/app/routers/settings.py` — 数据源设置 API（或扩展已有）
- `frontend/src/views/RealtimeMonitor.vue` — 实时监控页
- `frontend/src/api/realtime.ts` — 实时 API 调用
- `frontend/src/components/realtime/IndexChart.vue` — 指数分时图
- `frontend/src/components/realtime/NorthFlowChart.vue` — 北向资金图
- `frontend/src/components/realtime/SectorRanking.vue` — 板块排行
- `frontend/src/components/realtime/PositionMonitor.vue` — 持仓监控
- `frontend/src/components/realtime/RealtimeBar.vue` — 总览页实时条

**修改文件：**
- `backend/app/services/data/fetcher.py` — 改为委托给 Provider
- `backend/app/scheduler/trading_calendar.py` — 去掉 AKShare
- `backend/app/scheduler/setup.py` — 添加实时采集定时任务
- `backend/app/main.py` — 注册新路由
- `backend/requirements.txt` — 依赖变更
- `frontend/src/router/index.ts` — 添加 /realtime 路由
- `frontend/src/views/Dashboard.vue` — 顶部嵌入 RealtimeBar

### 错误处理

- 数据源请求失败时记录日志，返回空数据，不阻塞其他模块
- 实时采集连续失败 5 次后暂停 5 分钟再重试
- 前端显示"数据获取失败"提示，不白屏

### 测试

- Provider 单元测试：mock HTTP 响应，验证数据解析
- 实时 API 集成测试：验证端点返回正确格式
- 前端：实时条和监控页组件渲染测试
