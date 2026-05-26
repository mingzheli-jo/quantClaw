<template>
  <div class="realtime-bar" :class="{ closed: !summary.is_trading }">
    <div class="bar-indices">
      <div v-for="idx in summary.indices" :key="idx.code" class="bar-index">
        <span class="bar-idx-name">{{ idx.name }}</span>
        <span class="bar-idx-price">{{ idx.price.toFixed(2) }}</span>
        <span class="bar-idx-pct" :class="idx.change_pct >= 0 ? 'up' : 'down'">
          {{ idx.change_pct >= 0 ? '+' : '' }}{{ idx.change_pct.toFixed(2) }}%
        </span>
      </div>
    </div>
    <div class="bar-extra">
      <div class="bar-north" v-if="summary.north_flow?.net_amount !== undefined">
        <span class="bar-label">北向</span>
        <span :class="summary.north_flow.net_amount >= 0 ? 'up' : 'down'">
          {{ formatFlow(summary.north_flow.net_amount) }}
        </span>
      </div>
      <div class="bar-status" v-if="!summary.is_trading">
        已收盘
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { fetchRealtimeSummary, type RealtimeSummary } from '@/api/realtime'

const summary = ref<RealtimeSummary>({
  indices: [], north_flow: {} as any,
  sectors: { gainers: [], fund_inflow: [] },
  is_trading: false, last_refresh: null,
})

let timer: ReturnType<typeof setInterval> | null = null

function formatFlow(val: number): string {
  const abs = Math.abs(val)
  const sign = val >= 0 ? '+' : '-'
  if (abs >= 1e8) return `${sign}${(abs / 1e8).toFixed(1)}亿`
  if (abs >= 1e4) return `${sign}${(abs / 1e4).toFixed(0)}万`
  return `${sign}${abs.toFixed(0)}`
}

async function refresh() {
  try {
    const { data } = await fetchRealtimeSummary()
    summary.value = data
  } catch {}
}

onMounted(() => {
  refresh()
  timer = setInterval(refresh, 60_000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.realtime-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  background: var(--color-surface-elevated, #1a1f2e);
  border-radius: 12px;
  margin-bottom: 20px;
  gap: 16px;
  flex-wrap: wrap;
}
.realtime-bar.closed {
  opacity: 0.7;
}
.bar-indices {
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
}
.bar-index {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.bar-idx-name {
  font-size: 13px;
  color: var(--color-text-muted, #8b95a5);
}
.bar-idx-price {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text, #e0e6ed);
}
.bar-idx-pct {
  font-size: 13px;
  font-weight: 500;
}
.bar-extra {
  display: flex;
  gap: 16px;
  align-items: center;
}
.bar-label {
  font-size: 13px;
  color: var(--color-text-muted, #8b95a5);
  margin-right: 4px;
}
.bar-status {
  font-size: 12px;
  color: var(--color-text-muted, #8b95a5);
  background: rgba(255,255,255,0.05);
  padding: 2px 10px;
  border-radius: 4px;
}
.up { color: #ef4444; }
.down { color: #22c55e; }
</style>
