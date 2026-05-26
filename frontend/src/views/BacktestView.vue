<template>
  <div class="backtest-page">
    <h1 class="page-title">策略回测</h1>

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

    <template v-if="result && result.status === 'completed' && result.summary">
      <div class="summary-grid">
        <div class="card summary-card" v-for="item in summaryItems" :key="item.label">
          <div class="summary-label">{{ item.label }}</div>
          <div class="summary-value" :class="item.colorClass">{{ item.value }}</div>
        </div>
      </div>

      <div class="card chart-card">
        <h2 class="section-title">收益曲线</h2>
        <div ref="chartRef" class="equity-chart" />
      </div>

      <div class="card trades-card" v-if="result.trades && result.trades.length > 0">
        <h2 class="section-title">交易明细 ({{ result.trades.length }} 笔)</h2>
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
    yAxis: {
      type: 'value',
      axisLabel: { color: '#8b95a5', fontSize: 11, formatter: (v: number) => `¥${(v / 1000).toFixed(0)}k` },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
    },
    tooltip: {
      trigger: 'axis',
      formatter: (p: any) => `${p[0].name}<br/>净值: ¥${p[0].value.toLocaleString()}<br/>收益: ${((p[0].value - initVal) / initVal * 100).toFixed(1)}%`,
    },
    series: [{
      type: 'line', data: dv.map(d => d.value), smooth: true, symbol: 'none',
      lineStyle: { color: '#3b82f6', width: 2 },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(59, 130, 246, 0.3)' },
          { offset: 1, color: 'rgba(59, 130, 246, 0.02)' },
        ]),
      },
    }],
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
  } catch {
    running.value = false
  }
}

async function loadResult(id: number) {
  const { data } = await getBacktest(id)
  result.value = data
  await nextTick()
  renderChart()
}

async function loadHistory() {
  try {
    const { data } = await listBacktests()
    history.value = data
  } catch {}
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
.config-panel { padding: 16px 20px; margin-bottom: 20px; }
.config-row { display: flex; gap: 16px; align-items: flex-end; flex-wrap: wrap; }
.config-field { display: flex; flex-direction: column; gap: 4px; }
.config-field label { font-size: 12px; color: #8b95a5; }
.form-select, .form-input { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 6px; padding: 8px 12px; color: #e0e6ed; font-size: 14px; min-width: 140px; }
.btn-primary { background: #3b82f6; color: #fff; border: none; border-radius: 8px; padding: 8px 20px; font-size: 14px; font-weight: 500; cursor: pointer; white-space: nowrap; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.summary-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; }
.summary-card { padding: 14px 16px; }
.summary-label { font-size: 12px; color: #8b95a5; margin-bottom: 4px; }
.summary-value { font-size: 20px; font-weight: 700; }
.chart-card { padding: 16px 20px; margin-bottom: 20px; }
.section-title { font-size: 16px; font-weight: 600; margin-bottom: 12px; }
.equity-chart { width: 100%; height: 300px; }
.trades-card { padding: 16px 20px; margin-bottom: 20px; }
.trades-table-wrapper { overflow-x: auto; }
.trades-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.trades-table th { text-align: left; padding: 8px 10px; color: #8b95a5; border-bottom: 1px solid rgba(255,255,255,0.08); font-weight: 500; }
.trades-table td { padding: 8px 10px; border-bottom: 1px solid rgba(255,255,255,0.04); }
.trade-code { font-size: 11px; color: #8b95a5; margin-left: 4px; }
.error-card { padding: 20px; color: #ef4444; margin-bottom: 20px; }
.history-card { padding: 16px 20px; }
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
