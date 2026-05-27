<template>
  <div class="stock-detail">
    <!-- Back + Title -->
    <div class="detail-header">
      <button class="back-btn" @click="router.back()">
        <el-icon :size="18"><ArrowLeft /></el-icon>
        <span>返回</span>
      </button>
      <div class="stock-title" v-if="score">
        <h2 class="stock-name">{{ score.stock_name }}</h2>
        <span class="stock-code">{{ score.code }}</span>
        <span class="total-score">综合 {{ score.score?.toFixed(1) }}</span>
        <el-button
          :type="isWatched ? 'warning' : 'default'"
          :icon="isWatched ? StarFilled : Star"
          circle
          size="small"
          @click="toggleWatchlist"
          :title="isWatched ? '取消自选' : '加入自选'"
        />
      </div>
    </div>

    <!-- K-Line + Radar row -->
    <div class="chart-row">
      <div class="card card-kline">
        <div class="card-title">K线走势（60日）</div>
        <div ref="klineContainer" class="kline-chart" />
      </div>

      <div class="card card-radar">
        <div class="card-title">评分雷达</div>
        <div ref="radarRef" class="radar-chart" />
        <div class="radar-breakdown" v-if="score">
          <div class="rb-item">
            <span class="rb-label">技术</span>
            <div class="rb-bar"><div class="rb-fill" :style="{ width: score.tech_score + '%', background: '#4ecdc4' }" /></div>
            <span class="rb-val">{{ score.tech_score?.toFixed(1) }}</span>
          </div>
          <div class="rb-item">
            <span class="rb-label">资金</span>
            <div class="rb-bar"><div class="rb-fill" :style="{ width: score.fund_score + '%', background: '#ffa726' }" /></div>
            <span class="rb-val">{{ score.fund_score?.toFixed(1) }}</span>
          </div>
          <div class="rb-item">
            <span class="rb-label">动量</span>
            <div class="rb-bar"><div class="rb-fill" :style="{ width: score.momentum_score + '%', background: '#7c4dff' }" /></div>
            <span class="rb-val">{{ score.momentum_score?.toFixed(1) }}</span>
          </div>
          <div class="rb-item">
            <span class="rb-label">情绪</span>
            <div class="rb-bar"><div class="rb-fill" :style="{ width: score.sentiment_score + '%', background: '#ef5350' }" /></div>
            <span class="rb-val">{{ score.sentiment_score?.toFixed(1) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Score reason -->
    <div class="card card-reason" v-if="score?.reason">
      <div class="card-title">选股理由</div>
      <p class="reason-text">{{ score.reason }}</p>
    </div>

    <!-- Signal history -->
    <div class="card card-signals">
      <div class="card-title">历史信号</div>
      <el-table :data="signalList" class="dark-table" v-if="signalList.length > 0">
        <el-table-column prop="trade_date" label="日期" width="120" />
        <el-table-column prop="direction" label="方向" width="80" align="center">
          <template #default="{ row }">
            <span class="sig-dir" :class="row.direction">
              {{ row.direction === 'buy' ? '买入' : '卖出' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="score" label="评分" width="80" align="center">
          <template #default="{ row }">
            <span class="mono">{{ row.score?.toFixed(1) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="reason" label="理由" min-width="300" show-overflow-tooltip />
      </el-table>
      <div v-else class="empty-hint">暂无历史信号</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Star, StarFilled } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { createChart, type IChartApi } from 'lightweight-charts'
import { fetchKline, fetchScore, fetchSignals, type KlineItem, type StockScore, type StockSignal } from '@/api/stock'
import { addToWatchlist, removeFromWatchlist, fetchWatchlist } from '@/api/watchlist'

const route = useRoute()
const router = useRouter()
const code = route.params.code as string

const klineContainer = ref<HTMLElement>()
const radarRef = ref<HTMLElement>()
let lwChart: IChartApi | null = null
let radarChart: echarts.ECharts | null = null

const score = ref<StockScore | null>(null)
const signalList = ref<StockSignal[]>([])
const isWatched = ref(false)

async function checkWatchlist() {
  try {
    const { data } = await fetchWatchlist()
    isWatched.value = data.some((w: { code: string }) => w.code === code)
  } catch {}
}

async function toggleWatchlist() {
  if (isWatched.value) {
    await removeFromWatchlist(code)
    isWatched.value = false
  } else {
    await addToWatchlist(code)
    isWatched.value = true
  }
}

function calcMA(data: KlineItem[], period: number): (number | null)[] {
  return data.map((_, i) => {
    if (i < period - 1) return null
    let sum = 0
    for (let j = 0; j < period; j++) {
      sum += data[i - j].close
    }
    return sum / period
  })
}

function initKline(klines: KlineItem[], sigs: StockSignal[]) {
  if (!klineContainer.value) return

  lwChart = createChart(klineContainer.value, {
    width: klineContainer.value.clientWidth,
    height: 420,
    layout: {
      background: { color: 'transparent' },
      textColor: '#8888a8',
      fontSize: 11,
    },
    grid: {
      vertLines: { color: 'rgba(42, 42, 74, 0.4)' },
      horzLines: { color: 'rgba(42, 42, 74, 0.4)' },
    },
    crosshair: {
      mode: 0,
    },
    rightPriceScale: {
      borderColor: '#2a2a4a',
    },
    timeScale: {
      borderColor: '#2a2a4a',
      timeVisible: false,
    },
  })

  // A-share convention: RED = up, GREEN = down
  const candleSeries = lwChart.addCandlestickSeries({
    upColor: '#ef5350',
    downColor: '#26a69a',
    borderUpColor: '#ef5350',
    borderDownColor: '#26a69a',
    wickUpColor: '#ef5350',
    wickDownColor: '#26a69a',
  })

  const candleData = klines.map((k) => ({
    time: k.trade_date as string,
    open: k.open,
    high: k.high,
    low: k.low,
    close: k.close,
  }))
  candleSeries.setData(candleData)

  // Volume histogram
  const volumeSeries = lwChart.addHistogramSeries({
    priceFormat: { type: 'volume' },
    priceScaleId: 'volume',
  })
  lwChart.priceScale('volume').applyOptions({
    scaleMargins: { top: 0.85, bottom: 0 },
  })
  volumeSeries.setData(
    klines.map((k) => ({
      time: k.trade_date as string,
      value: k.volume,
      color: k.close >= k.open ? 'rgba(239, 83, 80, 0.4)' : 'rgba(38, 166, 154, 0.4)',
    }))
  )

  // MA lines
  const ma5 = calcMA(klines, 5)
  const ma10 = calcMA(klines, 10)
  const ma20 = calcMA(klines, 20)

  const addMA = (values: (number | null)[], color: string) => {
    const series = lwChart!.addLineSeries({
      color,
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    })
    const lineData = values
      .map((v, i) => (v !== null ? { time: klines[i].trade_date as string, value: v } : null))
      .filter((d): d is { time: string; value: number } => d !== null)
    series.setData(lineData)
  }

  addMA(ma5, '#ffa726')
  addMA(ma10, '#42a5f5')
  addMA(ma20, '#ab47bc')

  // Signal markers on candlestick
  const markers = sigs
    .filter((s) => klines.some((k) => k.trade_date === s.trade_date))
    .map((s) => ({
      time: s.trade_date as string,
      position: s.direction === 'buy' ? ('belowBar' as const) : ('aboveBar' as const),
      color: s.direction === 'buy' ? '#ef5350' : '#26a69a',
      shape: s.direction === 'buy' ? ('arrowUp' as const) : ('arrowDown' as const),
      text: s.direction === 'buy' ? 'B' : 'S',
    }))
    .sort((a, b) => (a.time < b.time ? -1 : 1))

  if (markers.length > 0) {
    candleSeries.setMarkers(markers)
  }

  lwChart.timeScale().fitContent()
}

function initRadar(s: StockScore) {
  if (!radarRef.value) return
  radarChart = echarts.init(radarRef.value)

  radarChart.setOption({
    radar: {
      indicator: [
        { name: '技术', max: 100 },
        { name: '资金', max: 100 },
        { name: '动量', max: 100 },
        { name: '情绪', max: 100 },
      ],
      shape: 'polygon',
      splitNumber: 4,
      axisName: { color: '#8888a8', fontSize: 12 },
      splitArea: {
        areaStyle: {
          color: ['rgba(78, 205, 196, 0.02)', 'rgba(78, 205, 196, 0.04)', 'rgba(78, 205, 196, 0.06)', 'rgba(78, 205, 196, 0.08)'],
        },
      },
      splitLine: { lineStyle: { color: '#2a2a4a' } },
      axisLine: { lineStyle: { color: '#2a2a4a' } },
    },
    series: [{
      type: 'radar',
      data: [{
        value: [s.tech_score, s.fund_score, s.momentum_score, s.sentiment_score],
        areaStyle: { color: 'rgba(78, 205, 196, 0.2)' },
        lineStyle: { color: '#4ecdc4', width: 2 },
        itemStyle: { color: '#4ecdc4' },
      }],
    }],
  })
}

function handleResize() {
  if (lwChart && klineContainer.value) {
    lwChart.applyOptions({ width: klineContainer.value.clientWidth })
  }
  radarChart?.resize()
}

onMounted(async () => {
  let klines: KlineItem[] = []

  try {
    const [klineRes, scoreRes, sigRes] = await Promise.all([
      fetchKline(code, 60),
      fetchScore(code),
      fetchSignals(code),
    ])
    klines = klineRes.data
    score.value = scoreRes.data
    signalList.value = sigRes.data
  } catch {
    // API unavailable
  }

  await checkWatchlist()

  await nextTick()
  initKline(klines, signalList.value)
  if (score.value) {
    initRadar(score.value)
  }

  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  lwChart?.remove()
  radarChart?.dispose()
})
</script>

<style scoped>
.stock-detail {
  width: 100%;
}

.card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 20px;
}

.card-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--color-text);
  margin-bottom: 16px;
}

.mono { font-variant-numeric: tabular-nums; }

/* -- Header -- */
.detail-header {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-bottom: 20px;
}

.back-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  background: none;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  color: var(--color-text-secondary);
  padding: 6px 12px;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s;
}

.back-btn:hover {
  border-color: var(--color-accent);
  color: var(--color-accent);
}

.stock-title {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.stock-name {
  font-size: 22px;
  font-weight: 800;
  color: var(--color-text);
}

.stock-code {
  font-size: 14px;
  color: var(--color-text-secondary);
  font-variant-numeric: tabular-nums;
}

.total-score {
  font-size: 14px;
  font-weight: 700;
  color: var(--color-accent);
  background: rgba(78, 205, 196, 0.1);
  padding: 3px 10px;
  border-radius: 6px;
}

/* -- Charts row -- */
.chart-row {
  display: flex;
  gap: 20px;
}

.card-kline {
  flex: 1;
  min-width: 0;
}

.kline-chart {
  width: 100%;
  height: 420px;
}

.card-radar {
  width: 320px;
  flex-shrink: 0;
}

.radar-chart {
  width: 100%;
  height: 220px;
}

/* -- Radar breakdown bars -- */
.radar-breakdown {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 8px;
}

.rb-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.rb-label {
  font-size: 12px;
  color: var(--color-text-secondary);
  width: 32px;
  flex-shrink: 0;
}

.rb-bar {
  flex: 1;
  height: 6px;
  background: rgba(42, 42, 74, 0.6);
  border-radius: 3px;
  overflow: hidden;
}

.rb-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.6s cubic-bezier(0.16, 1, 0.3, 1);
}

.rb-val {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text);
  width: 32px;
  text-align: right;
  font-variant-numeric: tabular-nums;
}

/* -- Reason -- */
.reason-text {
  font-size: 14px;
  line-height: 1.7;
  color: var(--color-text-secondary);
}

/* -- Signals table -- */
.dark-table {
  --el-table-bg-color: transparent;
  --el-table-tr-bg-color: transparent;
  --el-table-header-bg-color: rgba(42, 42, 74, 0.3);
  --el-table-row-hover-bg-color: var(--color-surface-hover);
  --el-table-border-color: var(--color-border);
  --el-table-text-color: var(--color-text);
  --el-table-header-text-color: var(--color-text-secondary);
  --el-fill-color-lighter: transparent;
}

.sig-dir {
  font-size: 12px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 4px;
}

.sig-dir.buy {
  background: rgba(239, 83, 80, 0.12);
  color: var(--color-danger);
}

.sig-dir.sell {
  background: rgba(38, 166, 154, 0.12);
  color: var(--color-success);
}

.empty-hint {
  text-align: center;
  color: var(--color-text-secondary);
  padding: 32px 0;
  font-size: 14px;
}
</style>
