<template>
  <header class="app-header">
    <h1 class="page-title">{{ pageTitle }}</h1>
    <div class="header-right">
      <div class="stock-search">
        <el-autocomplete
          v-model="searchQuery"
          :fetch-suggestions="handleSearch"
          placeholder="搜索股票代码/名称"
          :trigger-on-focus="false"
          :debounce="300"
          clearable
          @select="handleSelect"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
          <template #default="{ item }">
            <div class="search-item">
              <span class="search-code">{{ item.value }}</span>
              <span class="search-name">{{ item.label }}</span>
              <span class="search-industry">{{ item.industry }}</span>
            </div>
          </template>
        </el-autocomplete>
      </div>
      <span class="header-date">{{ dateStr }}</span>
    </div>
  </header>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Search } from '@element-plus/icons-vue'
import { searchStocks } from '@/api/stock'

const route = useRoute()
const router = useRouter()
const searchQuery = ref('')

const titleMap: Record<string, string> = {
  dashboard: '仪表盘',
  scan: '选股扫描',
  stock: '个股详情',
  position: '持仓管理',
  realtime: '实时监控',
  backtest: '策略回测',
  learn: '学习中心',
  settings: '系统设置',
}

const pageTitle = computed(() => {
  const name = route.name as string
  return titleMap[name] ?? '量化信号'
})

const dateStr = computed(() => {
  const d = new Date()
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const weekDays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  return `${y}-${m}-${day} ${weekDays[d.getDay()]}`
})

async function handleSearch(query: string, cb: (results: { value: string; label: string; industry: string }[]) => void) {
  if (!query || query.length < 1) {
    cb([])
    return
  }
  try {
    const { data } = await searchStocks(query)
    cb(data.map(s => ({ value: s.code, label: s.name, industry: s.industry })))
  } catch {
    cb([])
  }
}

function handleSelect(item: { value: string }) {
  searchQuery.value = ''
  router.push(`/stock/${item.value}`)
}
</script>

<style scoped>
.app-header {
  height: 64px;
  padding: 0 32px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-surface);
}

.page-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--color-text);
  letter-spacing: 0.3px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.stock-search :deep(.el-autocomplete) {
  width: 280px;
}

.stock-search :deep(.el-input__wrapper) {
  background: var(--color-bg);
  border-radius: 8px;
  box-shadow: none;
  border: 1px solid var(--color-border);
  transition: border-color 0.2s;
}

.stock-search :deep(.el-input__wrapper:hover),
.stock-search :deep(.el-input__wrapper.is-focus) {
  border-color: var(--color-accent);
}

.stock-search :deep(.el-input__inner) {
  color: var(--color-text);
  font-size: 13px;
}

.stock-search :deep(.el-input__inner::placeholder) {
  color: var(--color-text-secondary);
}

.stock-search :deep(.el-input__prefix .el-icon) {
  color: var(--color-text-secondary);
}

.search-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 2px 0;
}

.search-code {
  font-weight: 600;
  font-size: 13px;
  color: var(--color-accent);
  min-width: 65px;
  font-variant-numeric: tabular-nums;
}

.search-name {
  font-size: 13px;
  color: var(--color-text);
  flex: 1;
}

.search-industry {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.header-date {
  font-size: 13px;
  color: var(--color-text-secondary);
  font-variant-numeric: tabular-nums;
}
</style>
