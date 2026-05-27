<template>
  <div class="watchlist-page">
    <div class="page-header">
      <h2>自选股</h2>
      <span class="stock-count">{{ items.length }} 只</span>
    </div>

    <el-table :data="items" stripe @row-click="goDetail" style="cursor: pointer">
      <el-table-column prop="code" label="代码" width="100">
        <template #default="{ row }">
          <span class="code-cell">{{ row.code }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="name" label="名称" width="140" />
      <el-table-column prop="industry" label="行业" width="100" />
      <el-table-column label="现价" width="100">
        <template #default="{ row }">{{ row.close.toFixed(2) }}</template>
      </el-table-column>
      <el-table-column label="涨跌幅" width="100">
        <template #default="{ row }">
          <span :class="row.change_pct >= 0 ? 'up' : 'down'">
            {{ row.change_pct >= 0 ? '+' : '' }}{{ (row.change_pct ?? 0).toFixed(2) }}%
          </span>
        </template>
      </el-table-column>
      <el-table-column label="评分" width="80">
        <template #default="{ row }">
          <span class="score-badge">{{ row.score }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-button size="small" @click.stop="goCompare(row.code)">对比</el-button>
          <el-button size="small" type="danger" plain @click.stop="handleRemove(row.code)">移除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { fetchWatchlist, removeFromWatchlist, type WatchlistItem } from '@/api/watchlist'

const router = useRouter()
const items = ref<WatchlistItem[]>([])

async function load() {
  const { data } = await fetchWatchlist()
  items.value = data
}

function goDetail(row: WatchlistItem) {
  router.push(`/stock/${row.code}`)
}

function goCompare(code: string) {
  router.push(`/compare?codes=${code}`)
}

async function handleRemove(code: string) {
  await removeFromWatchlist(code)
  items.value = items.value.filter(i => i.code !== code)
}

onMounted(load)
</script>

<style scoped>
.page-header { display: flex; align-items: baseline; gap: 12px; margin-bottom: 20px; }
.page-header h2 { font-size: 20px; font-weight: 700; color: var(--color-text); }
.stock-count { font-size: 14px; color: var(--color-text-secondary); }
.code-cell { font-variant-numeric: tabular-nums; font-weight: 600; color: var(--color-accent); }
.up { color: var(--color-danger, #ef5350); }
.down { color: var(--color-success, #4ecdc4); }
.score-badge { font-weight: 600; }
</style>
