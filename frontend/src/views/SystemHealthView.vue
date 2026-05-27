<template>
  <div class="system-health">
    <div class="summary-cards">
      <div class="summary-card" :class="statusClass">
        <div class="card-label">今日状态</div>
        <div class="card-value">{{ statusText }}</div>
      </div>
      <div class="summary-card">
        <div class="card-label">上次成功</div>
        <div class="card-value">{{ lastSuccessText }}</div>
      </div>
      <div class="summary-card">
        <div class="card-label">今日任务</div>
        <div class="card-value">{{ summary?.today_jobs ?? 0 }}</div>
      </div>
    </div>

    <el-table :data="logs" stripe style="width: 100%; margin-top: 24px">
      <el-table-column prop="job_name" label="任务" width="200" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'success' ? 'success' : row.status === 'partial' ? 'warning' : 'danger'" size="small">
            {{ row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="records_collected" label="记录数" width="100" />
      <el-table-column prop="message" label="消息" />
      <el-table-column label="开始时间" width="180">
        <template #default="{ row }">{{ row.started_at?.slice(0, 19) }}</template>
      </el-table-column>
      <el-table-column label="耗时" width="100">
        <template #default="{ row }">{{ duration(row) }}</template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { fetchHealth, fetchHealthSummary, type HealthLog, type HealthSummary } from '@/api/system'

const logs = ref<HealthLog[]>([])
const summary = ref<HealthSummary | null>(null)

const statusText = computed(() => {
  const s = summary.value?.today_status
  if (s === 'success') return '正常'
  if (s === 'partial') return '部分缺失'
  if (s === 'failed') return '失败'
  return '无数据'
})

const statusClass = computed(() => {
  const s = summary.value?.today_status
  if (s === 'success') return 'status-ok'
  if (s === 'partial') return 'status-warn'
  if (s === 'failed') return 'status-error'
  return 'status-none'
})

const lastSuccessText = computed(() => {
  if (!summary.value?.last_success) return '无记录'
  const d = new Date(summary.value.last_success)
  const now = new Date()
  const hours = Math.round((now.getTime() - d.getTime()) / 3600000)
  if (hours < 1) return '刚刚'
  if (hours < 24) return `${hours}小时前`
  return `${Math.round(hours / 24)}天前`
})

function duration(row: HealthLog): string {
  if (!row.started_at || !row.finished_at) return '-'
  const ms = new Date(row.finished_at).getTime() - new Date(row.started_at).getTime()
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

onMounted(async () => {
  const [healthRes, summaryRes] = await Promise.all([fetchHealth(), fetchHealthSummary()])
  logs.value = healthRes.data.logs
  summary.value = summaryRes.data
})
</script>

<style scoped>
.summary-cards {
  display: flex;
  gap: 16px;
}
.summary-card {
  flex: 1;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  padding: 20px;
}
.card-label { font-size: 13px; color: var(--color-text-secondary); margin-bottom: 8px; }
.card-value { font-size: 24px; font-weight: 700; color: var(--color-text); }
.status-ok .card-value { color: var(--color-success, #4ecdc4); }
.status-warn .card-value { color: var(--color-warning, #f4a261); }
.status-error .card-value { color: var(--color-danger, #ef5350); }
.status-none .card-value { color: var(--color-text-secondary); }
</style>
