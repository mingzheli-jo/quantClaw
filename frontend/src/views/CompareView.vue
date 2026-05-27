<template>
  <div class="compare-page">
    <div class="page-header">
      <h2>个股对比</h2>
    </div>

    <div class="stock-picker">
      <el-autocomplete
        v-model="searchInput"
        :fetch-suggestions="handleSearch"
        placeholder="搜索添加股票 (最多4只)"
        :trigger-on-focus="false"
        :debounce="300"
        clearable
        @select="handleAdd"
        style="width: 300px"
      />
      <div class="selected-tags">
        <el-tag v-for="code in selectedCodes" :key="code" closable @close="handleRemove(code)" size="large">
          {{ stockNames[code] || code }}
        </el-tag>
      </div>
    </div>

    <div v-if="stocks.length >= 2" class="compare-content">
      <div class="section-title">评分对比</div>
      <div class="radar-container" ref="radarRef" style="height: 350px" />

      <div class="section-title">走势对比 (涨跌幅 %)</div>
      <div class="kline-container" ref="klineRef" style="height: 350px" />

      <div class="section-title">详细评分</div>
      <el-table :data="scoreRows" stripe>
        <el-table-column prop="dimension" label="维度" width="120" />
        <el-table-column v-for="s in stocks" :key="s.code" :label="`${s.name} (${s.code})`">
          <template #default="{ row }">{{ row[s.code] }}</template>
        </el-table-column>
      </el-table>
    </div>

    <div v-else class="empty-hint">请添加至少 2 只股票进行对比</div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import * as echarts from 'echarts'
import { searchStocks, fetchCompare, type CompareStock } from '@/api/stock'

const route = useRoute()
const searchInput = ref('')
const selectedCodes = ref<string[]>([])
const stocks = ref<CompareStock[]>([])
const stockNames = ref<Record<string, string>>({})
const radarRef = ref<HTMLElement>()
const klineRef = ref<HTMLElement>()
let radarChart: echarts.ECharts | null = null
let klineChart: echarts.ECharts | null = null

const scoreRows = computed(() => {
  const dims = [
    { key: 'score', label: '总分' },
    { key: 'tech_score', label: '技术面' },
    { key: 'fund_score', label: '资金面' },
    { key: 'momentum_score', label: '动量' },
    { key: 'sentiment_score', label: '情绪面' },
  ]
  return dims.map(d => {
    const row: Record<string, string | number> = { dimension: d.label }
    for (const s of stocks.value) {
      row[s.code] = (s as Record<string, unknown>)[d.key] as number
    }
    return row
  })
})

async function handleSearch(query: string, cb: (r: { value: string; label: string }[]) => void) {
  if (!query) { cb([]); return }
  try {
    const { data } = await searchStocks(query)
    cb(data.map(s => ({ value: s.code, label: s.name })))
  } catch { cb([]) }
}

async function handleAdd(item: { value: string; label: string }) {
  if (selectedCodes.value.length >= 4 || selectedCodes.value.includes(item.value)) return
  selectedCodes.value.push(item.value)
  stockNames.value[item.value] = item.label
  searchInput.value = ''
  await loadCompare()
}

function handleRemove(code: string) {
  selectedCodes.value = selectedCodes.value.filter(c => c !== code)
  loadCompare()
}

async function loadCompare() {
  if (selectedCodes.value.length < 2) { stocks.value = []; return }
  const { data } = await fetchCompare(selectedCodes.value)
  stocks.value = data
  for (const s of data) stockNames.value[s.code] = s.name
  await nextTick()
  renderRadar()
  renderKline()
}

function renderRadar() {
  if (!radarRef.value) return
  if (!radarChart) radarChart = echarts.init(radarRef.value)
  const indicators = [
    { name: '技术面', max: 40 }, { name: '资金面', max: 30 },
    { name: '动量', max: 20 }, { name: '情绪面', max: 10 },
  ]
  const series = stocks.value.map(s => ({
    name: s.name,
    value: [s.tech_score, s.fund_score, s.momentum_score, s.sentiment_score],
  }))
  radarChart.setOption({
    tooltip: {},
    legend: { data: stocks.value.map(s => s.name), bottom: 0 },
    radar: { indicator: indicators },
    series: [{ type: 'radar', data: series }],
  }, true)
}

function renderKline() {
  if (!klineRef.value || stocks.value.length < 2) return
  if (!klineChart) klineChart = echarts.init(klineRef.value)
  const dates = stocks.value[0].klines.map(k => k.trade_date)
  const series = stocks.value.map(s => {
    const base = s.klines[0]?.close || 1
    return {
      name: s.name,
      type: 'line' as const,
      data: s.klines.map(k => ((k.close - base) / base * 100).toFixed(2)),
      smooth: true,
    }
  })
  klineChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: stocks.value.map(s => s.name), bottom: 0 },
    xAxis: { type: 'category', data: dates },
    yAxis: { type: 'value', axisLabel: { formatter: '{value}%' } },
    series,
  }, true)
}

onMounted(() => {
  const initCodes = route.query.codes
  if (initCodes && typeof initCodes === 'string') {
    selectedCodes.value = initCodes.split(',').slice(0, 4)
    loadCompare()
  }
})
</script>

<style scoped>
.page-header { margin-bottom: 20px; }
.page-header h2 { font-size: 20px; font-weight: 700; color: var(--color-text); }
.stock-picker { display: flex; align-items: center; gap: 16px; margin-bottom: 24px; }
.selected-tags { display: flex; gap: 8px; }
.section-title { font-size: 16px; font-weight: 600; color: var(--color-text); margin: 24px 0 12px; }
.compare-content { margin-top: 16px; }
.empty-hint { text-align: center; color: var(--color-text-secondary); padding: 60px 0; font-size: 15px; }
</style>
