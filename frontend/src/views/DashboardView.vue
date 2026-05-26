<template>
  <div class="dashboard">
    <!-- Row 1: Temperature + Index cards -->
    <div class="dash-row dash-row-top">
      <div class="card card-gauge">
        <div class="card-label">市场温度</div>
        <div ref="gaugeRef" class="gauge-chart" />
        <div class="gauge-meta">
          <span class="gauge-val" :style="{ color: tempColor }">{{ overview.temperature ?? '--' }}</span>
          <span class="gauge-unit">/ 100</span>
        </div>
      </div>

      <div class="index-cards">
        <div
          v-for="idx in indexCards"
          :key="idx.label"
          class="card card-index"
        >
          <div class="idx-label">{{ idx.label }}</div>
          <div class="idx-value" :class="idx.value >= 0 ? 'up' : 'down'">
            {{ idx.value >= 0 ? '+' : '' }}{{ idx.value.toFixed(2) }}%
          </div>
        </div>

        <div class="card card-index">
          <div class="idx-label">涨停 / 跌停</div>
          <div class="idx-dual">
            <span class="up">{{ overview.limit_up ?? 0 }}</span>
            <span class="idx-sep">/</span>
            <span class="down">{{ overview.limit_down ?? 0 }}</span>
          </div>
        </div>

        <div class="card card-index">
          <div class="idx-label">北向净流入</div>
          <div class="idx-value" :class="(overview.north_net ?? 0) >= 0 ? 'up' : 'down'">
            {{ formatFlow(overview.north_net ?? 0) }}
          </div>
        </div>
      </div>
    </div>

    <!-- Row 2: Today signals -->
    <div class="section-header">
      <h2 class="section-title">今日信号</h2>
      <router-link to="/scan" class="section-link">查看全部 &rarr;</router-link>
    </div>
    <div class="signal-grid" v-if="signals.length > 0">
      <div v-for="sig in signals.slice(0, 6)" :key="sig.id" class="card card-signal">
        <div class="sig-top">
          <div class="sig-dir" :class="sig.direction">
            {{ sig.direction === 'buy' ? '买入' : '卖出' }}
          </div>
          <div class="sig-score">{{ sig.score.toFixed(1) }}</div>
        </div>
        <div class="sig-name">{{ sig.stock_name }}</div>
        <div class="sig-code">{{ sig.code }}</div>
        <div class="sig-reason">{{ sig.reason }}</div>
        <div class="sig-prices">
          <div class="sig-price-item">
            <span class="sig-price-label">建议区间</span>
            <span class="sig-price-val">{{ sig.suggested_buy_low?.toFixed(2) }} - {{ sig.suggested_buy_high?.toFixed(2) }}</span>
          </div>
          <div class="sig-price-item">
            <span class="sig-price-label">止损</span>
            <span class="sig-price-val down">{{ sig.stop_loss_price?.toFixed(2) }}</span>
          </div>
          <div class="sig-price-item">
            <span class="sig-price-label">目标</span>
            <span class="sig-price-val up">{{ sig.target_price?.toFixed(2) }}</span>
          </div>
        </div>
      </div>
    </div>
    <div v-else class="empty-hint">今日暂无信号</div>

    <!-- Row 3: Position summary + accuracy -->
    <div class="dash-row dash-row-bottom">
      <div class="card card-positions">
        <div class="card-label">持仓概览</div>
        <div class="pos-stats">
          <div class="pos-stat">
            <span class="pos-stat-val">{{ overview.active_positions ?? 0 }}</span>
            <span class="pos-stat-label">活跃持仓</span>
          </div>
          <div class="pos-divider" />
          <div class="pos-stat">
            <span
              class="pos-stat-val"
              :class="(overview.total_pnl ?? 0) >= 0 ? 'up' : 'down'"
            >
              {{ (overview.total_pnl ?? 0) >= 0 ? '+' : '' }}{{ (overview.total_pnl ?? 0).toFixed(2) }}%
            </span>
            <span class="pos-stat-label">总收益</span>
          </div>
        </div>
      </div>

      <div class="card card-accuracy">
        <div class="card-label">7日准确率</div>
        <div ref="accRef" class="acc-chart" />
        <div class="acc-value">{{ ((overview.signal_accuracy_7d ?? 0) * 100).toFixed(1) }}%</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import { fetchOverview, type OverviewData } from '@/api/dashboard'
import { fetchTodaySignals, type SignalItem } from '@/api/signal'

const gaugeRef = ref<HTMLElement>()
const accRef = ref<HTMLElement>()
let gaugeChart: echarts.ECharts | null = null
let accChart: echarts.ECharts | null = null

const overview = reactive<Partial<OverviewData>>({})
const signals = ref<SignalItem[]>([])

const tempColor = computed(() => {
  const t = overview.temperature ?? 50
  if (t <= 30) return 'var(--color-success)'
  if (t <= 70) return 'var(--color-warning)'
  return 'var(--color-danger)'
})

const indexCards = computed(() => [
  { label: '上证指数', value: overview.sh_index_pct ?? 0 },
  { label: '深证成指', value: overview.sz_index_pct ?? 0 },
  { label: '创业板指', value: overview.cyb_index_pct ?? 0 },
])

function formatFlow(val: number): string {
  if (Math.abs(val) >= 1e8) {
    return (val / 1e8).toFixed(2) + ' 亿'
  }
  if (Math.abs(val) >= 1e4) {
    return (val / 1e4).toFixed(1) + ' 万'
  }
  return val.toFixed(0)
}

function initGauge(temp: number) {
  if (!gaugeRef.value) return
  gaugeChart = echarts.init(gaugeRef.value)
  gaugeChart.setOption({
    series: [{
      type: 'gauge',
      startAngle: 210,
      endAngle: -30,
      min: 0,
      max: 100,
      radius: '92%',
      progress: {
        show: true,
        width: 14,
        roundCap: true,
        itemStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 1, y2: 0,
            colorStops: [
              { offset: 0, color: '#26a69a' },
              { offset: 0.5, color: '#ffa726' },
              { offset: 1, color: '#ef5350' },
            ],
          },
        },
      },
      axisLine: {
        lineStyle: {
          width: 14,
          color: [[1, 'rgba(42, 42, 74, 0.6)']],
        },
      },
      axisTick: { show: false },
      splitLine: { show: false },
      axisLabel: { show: false },
      pointer: { show: false },
      anchor: { show: false },
      title: { show: false },
      detail: { show: false },
      data: [{ value: temp }],
    }],
  })
}

function initAccuracy(rate: number) {
  if (!accRef.value) return
  accChart = echarts.init(accRef.value)
  const pct = rate * 100
  accChart.setOption({
    series: [{
      type: 'gauge',
      startAngle: 90,
      endAngle: -270,
      radius: '88%',
      progress: {
        show: true,
        width: 10,
        roundCap: true,
        itemStyle: { color: '#4ecdc4' },
      },
      axisLine: {
        lineStyle: {
          width: 10,
          color: [[1, 'rgba(42, 42, 74, 0.6)']],
        },
      },
      axisTick: { show: false },
      splitLine: { show: false },
      axisLabel: { show: false },
      pointer: { show: false },
      anchor: { show: false },
      title: { show: false },
      detail: { show: false },
      data: [{ value: pct }],
    }],
  })
}

function handleResize() {
  gaugeChart?.resize()
  accChart?.resize()
}

onMounted(async () => {
  try {
    const [overviewRes, signalRes] = await Promise.all([
      fetchOverview(),
      fetchTodaySignals(),
    ])
    Object.assign(overview, overviewRes.data)
    signals.value = signalRes.data
  } catch {
    // API not available, use empty defaults
  }

  initGauge(overview.temperature ?? 50)
  initAccuracy(overview.signal_accuracy_7d ?? 0)
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  gaugeChart?.dispose()
  accChart?.dispose()
})
</script>

<style scoped>
.dashboard {
  width: 100%;
}

.card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  padding: 20px;
}

.card-label {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin-bottom: 12px;
  font-weight: 500;
  letter-spacing: 0.3px;
}

.up { color: var(--color-danger); }
.down { color: var(--color-success); }

/* -- Row 1: Gauge + Index -- */
.dash-row-top {
  display: flex;
  gap: 20px;
  margin-bottom: 32px;
}

.card-gauge {
  width: 240px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.gauge-chart {
  width: 180px;
  height: 140px;
}

.gauge-meta {
  display: flex;
  align-items: baseline;
  gap: 4px;
  margin-top: -8px;
}

.gauge-val {
  font-size: 32px;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}

.gauge-unit {
  font-size: 13px;
  color: var(--color-text-secondary);
}

.index-cards {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
}

.card-index {
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-height: 100px;
}

.idx-label {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin-bottom: 8px;
}

.idx-value {
  font-size: 24px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.idx-dual {
  font-size: 24px;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 6px;
}

.idx-sep {
  color: var(--color-text-secondary);
  font-weight: 400;
  font-size: 18px;
}

/* -- Signals -- */
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.section-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--color-text);
}

.section-link {
  font-size: 13px;
  color: var(--color-accent);
  text-decoration: none;
  transition: opacity 0.2s;
}

.section-link:hover {
  opacity: 0.8;
}

.signal-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 16px;
  margin-bottom: 32px;
}

.card-signal {
  transition: border-color 0.2s ease, transform 0.2s ease;
  cursor: default;
}

.card-signal:hover {
  border-color: var(--color-accent);
  transform: translateY(-2px);
}

.sig-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.sig-dir {
  font-size: 12px;
  font-weight: 700;
  padding: 3px 10px;
  border-radius: 6px;
  letter-spacing: 0.5px;
}

.sig-dir.buy {
  background: rgba(239, 83, 80, 0.12);
  color: var(--color-danger);
}

.sig-dir.sell {
  background: rgba(38, 166, 154, 0.12);
  color: var(--color-success);
}

.sig-score {
  font-size: 20px;
  font-weight: 800;
  color: var(--color-accent);
  font-variant-numeric: tabular-nums;
}

.sig-name {
  font-size: 16px;
  font-weight: 700;
  color: var(--color-text);
  margin-bottom: 2px;
}

.sig-code {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-bottom: 8px;
  font-variant-numeric: tabular-nums;
}

.sig-reason {
  font-size: 12px;
  color: var(--color-text-secondary);
  line-height: 1.5;
  margin-bottom: 12px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.sig-prices {
  display: flex;
  gap: 12px;
  padding-top: 10px;
  border-top: 1px solid var(--color-border);
}

.sig-price-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.sig-price-label {
  font-size: 11px;
  color: var(--color-text-secondary);
}

.sig-price-val {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text);
  font-variant-numeric: tabular-nums;
}

.empty-hint {
  text-align: center;
  color: var(--color-text-secondary);
  padding: 48px 0;
  font-size: 14px;
  margin-bottom: 32px;
}

/* -- Row 3: Position + Accuracy -- */
.dash-row-bottom {
  display: flex;
  gap: 20px;
}

.card-positions {
  flex: 1;
}

.pos-stats {
  display: flex;
  align-items: center;
  gap: 32px;
  padding-top: 8px;
}

.pos-stat {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.pos-stat-val {
  font-size: 28px;
  font-weight: 800;
  color: var(--color-text);
  font-variant-numeric: tabular-nums;
}

.pos-stat-label {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.pos-divider {
  width: 1px;
  height: 40px;
  background: var(--color-border);
}

.card-accuracy {
  width: 200px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.acc-chart {
  width: 120px;
  height: 120px;
}

.acc-value {
  font-size: 22px;
  font-weight: 800;
  color: var(--color-accent);
  margin-top: -4px;
  font-variant-numeric: tabular-nums;
}
</style>
