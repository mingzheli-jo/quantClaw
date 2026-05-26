<template>
  <div class="scan-page">
    <!-- Ranking Table -->
    <div class="card card-table">
      <div class="card-top">
        <h2 class="card-title">综合评分排名</h2>
        <el-pagination
          v-model:current-page="page"
          :page-size="20"
          :total="total"
          layout="total, prev, pager, next"
          small
          background
          @current-change="loadRanking"
        />
      </div>

      <el-table
        :data="ranking"
        :row-class-name="tableRowClass"
        class="dark-table"
        @row-click="goStock"
        stripe
      >
        <el-table-column label="排名" width="60" align="center">
          <template #default="{ $index }">
            <span class="rank-num" :class="rankClass($index)">{{ (page - 1) * 20 + $index + 1 }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="code" label="代码" width="90">
          <template #default="{ row }">
            <span class="mono">{{ row.code }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="stock_name" label="名称" width="100" />
        <el-table-column prop="close_price" label="现价" width="80" align="right">
          <template #default="{ row }">
            <span class="mono">{{ row.close_price?.toFixed(2) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="score" label="综合" width="80" align="center" sortable>
          <template #default="{ row }">
            <span class="score-badge">{{ row.score?.toFixed(1) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="tech_score" label="技术" width="70" align="center" sortable>
          <template #default="{ row }">
            <span class="sub-score">{{ row.tech_score?.toFixed(1) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="fund_score" label="资金" width="70" align="center" sortable>
          <template #default="{ row }">
            <span class="sub-score">{{ row.fund_score?.toFixed(1) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="momentum_score" label="动量" width="70" align="center" sortable>
          <template #default="{ row }">
            <span class="sub-score">{{ row.momentum_score?.toFixed(1) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="sentiment_score" label="情绪" width="70" align="center" sortable>
          <template #default="{ row }">
            <span class="sub-score">{{ row.sentiment_score?.toFixed(1) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="reason" label="选股理由" min-width="200" show-overflow-tooltip />
      </el-table>
    </div>

    <!-- Bottom row: Sector Heatmap + North Flow -->
    <div class="scan-bottom">
      <div class="card card-sector">
        <h2 class="card-title">板块热力图</h2>
        <div ref="sectorRef" class="sector-chart" />
      </div>

      <div class="card card-flow">
        <h2 class="card-title">北向资金（30日）</h2>
        <div ref="flowRef" class="flow-chart" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import {
  fetchRanking,
  fetchSectors,
  fetchNorthFlow,
  type RankingItem,
  type SectorItem,
  type NorthFlowItem,
} from '@/api/scan'

const router = useRouter()

const ranking = ref<RankingItem[]>([])
const page = ref(1)
const total = ref(0)

const sectorRef = ref<HTMLElement>()
const flowRef = ref<HTMLElement>()
let sectorChart: echarts.ECharts | null = null
let flowChart: echarts.ECharts | null = null

function rankClass(index: number): string {
  const rank = (page.value - 1) * 20 + index
  if (rank === 0) return 'gold'
  if (rank === 1) return 'silver'
  if (rank === 2) return 'bronze'
  return ''
}

function tableRowClass({ rowIndex }: { row: RankingItem; rowIndex: number }): string {
  return rowIndex % 2 === 0 ? 'row-even' : 'row-odd'
}

function goStock(row: RankingItem) {
  router.push(`/stock/${row.code}`)
}

async function loadRanking(p?: number) {
  if (p !== undefined) page.value = p
  try {
    const { data } = await fetchRanking(page.value, 20)
    ranking.value = data.items
    total.value = data.total
  } catch {
    // API unavailable
  }
}

function initSectorChart(sectors: SectorItem[]) {
  if (!sectorRef.value) return
  sectorChart = echarts.init(sectorRef.value)

  const treeData = sectors.map((s) => ({
    name: s.sector,
    value: Math.abs(s.net_fund_flow),
    changePct: s.change_pct,
    itemStyle: {
      color: s.change_pct >= 0
        ? `rgba(239, 83, 80, ${Math.min(0.3 + Math.abs(s.change_pct) * 0.15, 0.9)})`
        : `rgba(38, 166, 154, ${Math.min(0.3 + Math.abs(s.change_pct) * 0.15, 0.9)})`,
    },
  }))

  sectorChart.setOption({
    tooltip: {
      backgroundColor: '#1a1a2e',
      borderColor: '#2a2a4a',
      textStyle: { color: '#e0e0e8', fontSize: 12 },
      formatter(params: { name: string; data: { changePct: number; value: number } }) {
        const d = params.data
        return `${params.name}<br/>涨跌: ${d.changePct >= 0 ? '+' : ''}${d.changePct?.toFixed(2)}%<br/>净流入: ${(d.value / 1e8).toFixed(2)}亿`
      },
    },
    series: [{
      type: 'treemap',
      data: treeData,
      width: '100%',
      height: '100%',
      roam: false,
      nodeClick: false,
      breadcrumb: { show: false },
      label: {
        show: true,
        color: '#e0e0e8',
        fontSize: 12,
        fontWeight: 600,
        formatter: '{b}\n{@changePct}%',
      },
      itemStyle: {
        borderColor: '#0f0f23',
        borderWidth: 2,
        gapWidth: 2,
      },
    }],
  })
}

function initFlowChart(flows: NorthFlowItem[]) {
  if (!flowRef.value) return
  flowChart = echarts.init(flowRef.value)

  const dates = flows.map((f) => f.trade_date)
  const values = flows.map((f) => f.net_amount / 1e8)

  flowChart.setOption({
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1a1a2e',
      borderColor: '#2a2a4a',
      textStyle: { color: '#e0e0e8', fontSize: 12 },
      formatter(params: { value: number; axisValue: string }[]) {
        const p = params[0]
        return `${p.axisValue}<br/>净流入: ${p.value.toFixed(2)}亿`
      },
    },
    grid: { left: 50, right: 16, top: 12, bottom: 28 },
    xAxis: {
      type: 'category',
      data: dates,
      axisLine: { lineStyle: { color: '#2a2a4a' } },
      axisLabel: { color: '#8888a8', fontSize: 11 },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      splitLine: { lineStyle: { color: '#2a2a4a', type: 'dashed' } },
      axisLabel: { color: '#8888a8', fontSize: 11, formatter: '{value}亿' },
    },
    series: [{
      type: 'line',
      data: values,
      smooth: true,
      symbol: 'none',
      lineStyle: { color: '#4ecdc4', width: 2 },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(78, 205, 196, 0.3)' },
          { offset: 1, color: 'rgba(78, 205, 196, 0.02)' },
        ]),
      },
    }],
  })
}

function handleResize() {
  sectorChart?.resize()
  flowChart?.resize()
}

onMounted(async () => {
  await loadRanking()

  try {
    const [sectorRes, flowRes] = await Promise.all([
      fetchSectors(),
      fetchNorthFlow(30),
    ])
    initSectorChart(sectorRes.data)
    initFlowChart(flowRes.data)
  } catch {
    // API unavailable
  }

  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  sectorChart?.dispose()
  flowChart?.dispose()
})
</script>

<style scoped>
.scan-page {
  width: 100%;
}

.card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 20px;
}

.card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.card-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--color-text);
}

.mono {
  font-variant-numeric: tabular-nums;
}

/* -- Table dark overrides -- */
.dark-table {
  --el-table-bg-color: transparent;
  --el-table-tr-bg-color: transparent;
  --el-table-header-bg-color: rgba(42, 42, 74, 0.3);
  --el-table-row-hover-bg-color: var(--color-surface-hover);
  --el-table-border-color: var(--color-border);
  --el-table-text-color: var(--color-text);
  --el-table-header-text-color: var(--color-text-secondary);
  --el-fill-color-lighter: transparent;
  cursor: pointer;
}

.dark-table :deep(.el-table__header th) {
  font-weight: 600;
  font-size: 12px;
  letter-spacing: 0.3px;
}

.dark-table :deep(.el-table__row) {
  transition: background 0.15s ease;
}

.dark-table :deep(.el-table__body tr.el-table__row--striped td.el-table__cell) {
  background: rgba(42, 42, 74, 0.15);
}

.rank-num {
  font-weight: 700;
  font-size: 13px;
  color: var(--color-text-secondary);
}

.rank-num.gold { color: #ffd700; }
.rank-num.silver { color: #c0c0c0; }
.rank-num.bronze { color: #cd7f32; }

.score-badge {
  display: inline-block;
  background: rgba(78, 205, 196, 0.12);
  color: var(--color-accent);
  font-weight: 700;
  font-size: 13px;
  padding: 2px 8px;
  border-radius: 6px;
  font-variant-numeric: tabular-nums;
}

.sub-score {
  font-size: 13px;
  color: var(--color-text-secondary);
  font-variant-numeric: tabular-nums;
}

/* -- Pagination dark overrides -- */
:deep(.el-pagination) {
  --el-pagination-bg-color: transparent;
  --el-pagination-text-color: var(--color-text-secondary);
  --el-pagination-button-bg-color: var(--color-surface-hover);
  --el-pagination-hover-color: var(--color-accent);
  --el-pagination-button-color: var(--color-text-secondary);
}

:deep(.el-pager li) {
  background: transparent !important;
}

:deep(.el-pager li.is-active) {
  color: var(--color-accent) !important;
}

/* -- Bottom charts -- */
.scan-bottom {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

.sector-chart {
  height: 320px;
}

.flow-chart {
  height: 320px;
}
</style>
