<template>
  <div class="learn-page">
    <el-tabs v-model="activeTab" class="dark-tabs">
      <el-tab-pane label="今日指标" name="today">
        <div class="card card-today" v-if="todayItem">
          <div class="today-header">
            <h2 class="today-name">{{ todayItem.name }}</h2>
            <span class="today-weight">系统权重: {{ todayItem.weight_in_system }}</span>
          </div>

          <div class="today-section">
            <h3 class="section-label">概述</h3>
            <p class="section-text">{{ todayItem.summary }}</p>
          </div>

          <div class="today-section" v-if="todayItem.formula">
            <h3 class="section-label">计算公式</h3>
            <div class="formula-box">{{ todayItem.formula }}</div>
          </div>

          <div class="today-grid">
            <div class="today-block buy-block">
              <h3 class="block-label">
                <span class="block-dot buy-dot" />
                买入形态
              </h3>
              <p class="block-text">{{ todayItem.buy_pattern }}</p>
            </div>
            <div class="today-block sell-block">
              <h3 class="block-label">
                <span class="block-dot sell-dot" />
                卖出形态
              </h3>
              <p class="block-text">{{ todayItem.sell_pattern }}</p>
            </div>
          </div>

          <div class="today-section">
            <h3 class="section-label">
              <el-icon :size="14" style="color: var(--color-warning); margin-right: 4px;"><WarningFilled /></el-icon>
              常见陷阱
            </h3>
            <p class="section-text trap-text">{{ todayItem.trap }}</p>
          </div>
        </div>
        <div v-else class="empty-hint">今日暂无学习内容</div>
      </el-tab-pane>

      <el-tab-pane label="指标归档" name="archive">
        <el-collapse class="dark-collapse" v-if="archiveList.length > 0">
          <el-collapse-item
            v-for="(item, idx) in archiveList"
            :key="idx"
            :name="idx"
          >
            <template #title>
              <div class="archive-title">
                <span class="archive-name">{{ item.name }}</span>
                <span class="archive-weight">{{ item.weight_in_system }}</span>
              </div>
            </template>

            <div class="archive-content">
              <div class="archive-section">
                <strong>概述</strong>
                <p>{{ item.summary }}</p>
              </div>
              <div class="archive-section" v-if="item.formula">
                <strong>公式</strong>
                <div class="formula-box">{{ item.formula }}</div>
              </div>
              <div class="archive-row">
                <div class="archive-half">
                  <strong class="up-label">买入形态</strong>
                  <p>{{ item.buy_pattern }}</p>
                </div>
                <div class="archive-half">
                  <strong class="down-label">卖出形态</strong>
                  <p>{{ item.sell_pattern }}</p>
                </div>
              </div>
              <div class="archive-section">
                <strong>常见陷阱</strong>
                <p class="trap-text">{{ item.trap }}</p>
              </div>
            </div>
          </el-collapse-item>
        </el-collapse>
        <div v-else class="empty-hint">暂无归档数据</div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { WarningFilled } from '@element-plus/icons-vue'
import { fetchToday, fetchArchive, type LearnItem } from '@/api/learn'

const activeTab = ref('today')
const todayItem = ref<LearnItem | null>(null)
const archiveList = ref<LearnItem[]>([])

onMounted(async () => {
  try {
    const [todayRes, archiveRes] = await Promise.all([
      fetchToday(),
      fetchArchive(),
    ])
    todayItem.value = todayRes.data
    archiveList.value = archiveRes.data
  } catch {
    // API unavailable
  }
})
</script>

<style scoped>
.learn-page {
  width: 100%;
}

.card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  padding: 24px;
}

/* -- Tabs overrides -- */
:deep(.el-tabs__nav-wrap::after) {
  background: var(--color-border) !important;
}

:deep(.el-tabs__item) {
  color: var(--color-text-secondary) !important;
  font-weight: 600;
}

:deep(.el-tabs__item.is-active) {
  color: var(--color-accent) !important;
}

:deep(.el-tabs__active-bar) {
  background: var(--color-accent) !important;
}

/* -- Today card -- */
.today-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--color-border);
}

.today-name {
  font-size: 22px;
  font-weight: 800;
  color: var(--color-text);
}

.today-weight {
  font-size: 13px;
  color: var(--color-accent);
  background: rgba(78, 205, 196, 0.1);
  padding: 4px 12px;
  border-radius: 6px;
  font-weight: 600;
}

.today-section {
  margin-bottom: 20px;
}

.section-label {
  font-size: 13px;
  font-weight: 700;
  color: var(--color-text-secondary);
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.section-text {
  font-size: 14px;
  line-height: 1.7;
  color: var(--color-text);
}

.formula-box {
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 14px 16px;
  font-family: 'Cascadia Code', 'Fira Code', monospace;
  font-size: 13px;
  color: var(--color-accent);
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.today-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 20px;
}

.today-block {
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: 10px;
  padding: 16px;
}

.block-label {
  font-size: 13px;
  font-weight: 700;
  color: var(--color-text);
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.block-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.buy-dot { background: var(--color-danger); }
.sell-dot { background: var(--color-success); }

.block-text {
  font-size: 13px;
  line-height: 1.6;
  color: var(--color-text-secondary);
}

.trap-text {
  color: var(--color-warning);
  opacity: 0.9;
}

/* -- Archive collapse -- */
:deep(.el-collapse) {
  border-top: none;
  border-bottom: none;
}

:deep(.el-collapse-item__header) {
  background: var(--color-surface) !important;
  border-bottom: 1px solid var(--color-border) !important;
  color: var(--color-text) !important;
  height: 56px;
  padding: 0 16px;
  font-size: 14px;
}

:deep(.el-collapse-item__wrap) {
  background: var(--color-surface) !important;
  border-bottom: 1px solid var(--color-border) !important;
}

:deep(.el-collapse-item__content) {
  color: var(--color-text);
  padding: 16px;
}

:deep(.el-collapse-item__arrow) {
  color: var(--color-text-secondary);
}

.archive-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding-right: 12px;
}

.archive-name {
  font-weight: 700;
}

.archive-weight {
  font-size: 12px;
  color: var(--color-accent);
  font-weight: 600;
}

.archive-content {
  font-size: 13px;
  line-height: 1.7;
}

.archive-section {
  margin-bottom: 14px;
}

.archive-section strong {
  display: block;
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.archive-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 14px;
}

.archive-half strong {
  display: block;
  font-size: 12px;
  margin-bottom: 4px;
}

.up-label { color: var(--color-danger); }
.down-label { color: var(--color-success); }

.archive-half p {
  color: var(--color-text-secondary);
}

.empty-hint {
  text-align: center;
  color: var(--color-text-secondary);
  padding: 48px 0;
  font-size: 14px;
}
</style>
