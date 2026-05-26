<template>
  <div class="realtime-page">
    <h1 class="page-title">实时监控</h1>
    <p class="page-status" :class="{ closed: !summary.is_trading }">
      {{ summary.is_trading ? '交易中' : '已收盘' }}
      <span v-if="summary.last_refresh" class="last-refresh">
        更新于 {{ formatTime(summary.last_refresh) }}
      </span>
    </p>

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
  indices: [], north_flow: {} as NorthFlowData,
  sectors: { gainers: [], fund_inflow: [] },
  is_trading: false, last_refresh: null,
})
const northFlow = ref<NorthFlowData>({} as NorthFlowData)
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
      formatter: (params: { name: string; value: number }[]) => {
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
  } catch {
    // silently handle refresh errors
  }
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
}
.idx-name { font-size: 13px; color: #8b95a5; margin-bottom: 6px; }
.idx-price { font-size: 24px; font-weight: 700; }
.idx-change { font-size: 14px; font-weight: 500; margin-top: 4px; }
.idx-amount { font-size: 12px; margin-left: 6px; opacity: 0.7; }

.north-card { padding: 16px 20px; }
.north-summary { display: flex; gap: 32px; margin-bottom: 16px; flex-wrap: wrap; }
.north-item { display: flex; flex-direction: column; gap: 4px; }
.north-label { font-size: 12px; color: #8b95a5; }
.north-val { font-size: 20px; font-weight: 700; }
.chart-container { width: 100%; height: 240px; }

.dual-section { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.dual-section .card { padding: 16px 20px; }
.ranking-list { display: flex; flex-direction: column; gap: 8px; }
.ranking-item { display: flex; align-items: center; gap: 10px; padding: 6px 0; border-bottom: 1px solid rgba(255,255,255,0.04); }
.rank-num { width: 20px; font-size: 13px; color: #8b95a5; font-weight: 600; }
.rank-name { flex: 1; font-size: 14px; }
.rank-val { font-size: 14px; font-weight: 500; }

.positions-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 16px; }
.position-card { padding: 16px; }
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
