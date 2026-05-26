<template>
  <div class="settings-page">
    <el-tabs v-model="activeTab" class="dark-tabs">
      <!-- Strategy Tab -->
      <el-tab-pane label="策略参数" name="strategy">
        <div class="card" v-if="strategyLoaded">
          <el-form label-width="140px" label-position="left" class="settings-form">
            <!-- Filter params -->
            <div class="param-group">
              <h3 class="group-title">筛选过滤</h3>
              <el-form-item v-for="(val, key) in strategy.filter" :key="'f-' + key" :label="filterLabels[key] || key">
                <el-input-number
                  :model-value="val"
                  @update:model-value="(v: number | undefined) => { if (v !== undefined) strategy.filter[key] = v }"
                  :precision="2"
                  controls-position="right"
                  style="width: 200px;"
                />
              </el-form-item>
            </div>

            <!-- Score params -->
            <div class="param-group">
              <h3 class="group-title">评分权重</h3>
              <el-form-item v-for="(val, key) in strategy.score" :key="'s-' + key" :label="scoreLabels[key] || key">
                <el-input-number
                  :model-value="val"
                  @update:model-value="(v: number | undefined) => { if (v !== undefined) strategy.score[key] = v }"
                  :precision="2"
                  :min="0"
                  :max="1"
                  :step="0.05"
                  controls-position="right"
                  style="width: 200px;"
                />
              </el-form-item>
            </div>

            <!-- Position params -->
            <div class="param-group">
              <h3 class="group-title">仓位管理</h3>
              <el-form-item v-for="(val, key) in strategy.position" :key="'p-' + key" :label="positionLabels[key] || key">
                <el-input-number
                  :model-value="val"
                  @update:model-value="(v: number | undefined) => { if (v !== undefined) strategy.position[key] = v }"
                  :precision="2"
                  controls-position="right"
                  style="width: 200px;"
                />
              </el-form-item>
            </div>

            <!-- Risk params -->
            <div class="param-group">
              <h3 class="group-title">风险控制</h3>
              <el-form-item v-for="(val, key) in strategy.risk" :key="'r-' + key" :label="riskLabels[key] || key">
                <el-input-number
                  :model-value="val"
                  @update:model-value="(v: number | undefined) => { if (v !== undefined) strategy.risk[key] = v }"
                  :precision="2"
                  controls-position="right"
                  style="width: 200px;"
                />
              </el-form-item>
            </div>

            <div class="form-actions">
              <el-button type="primary" :loading="saving" @click="saveStrategy">保存设置</el-button>
            </div>
          </el-form>
        </div>
        <div v-else class="empty-hint">加载中...</div>
      </el-tab-pane>

      <!-- Notification Tab -->
      <el-tab-pane label="通知设置" name="notify">
        <div class="card">
          <el-form label-width="140px" label-position="left" class="settings-form">
            <el-form-item label="飞书 Webhook">
              <el-input
                v-model="notifyUrl"
                placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/..."
                clearable
              />
            </el-form-item>
            <el-form-item label="测试通知">
              <div class="test-row">
                <el-input v-model="testMsg" placeholder="输入测试消息" style="flex: 1;" />
                <el-button :loading="testing" @click="handleTest">发送测试</el-button>
              </div>
            </el-form-item>
          </el-form>
        </div>
      </el-tab-pane>

      <!-- Account Tab -->
      <el-tab-pane label="账户设置" name="account">
        <div class="card">
          <el-form label-width="140px" label-position="left" class="settings-form">
            <el-form-item label="当前用户">
              <span class="account-val">{{ username }}</span>
            </el-form-item>
            <el-form-item label="修改密码">
              <el-input type="password" placeholder="新密码（功能开发中）" disabled />
            </el-form-item>
          </el-form>
          <div class="account-note">
            密码修改功能正在开发中，请联系管理员修改密码。
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import {
  getStrategy,
  updateStrategy,
  getNotify,
  testNotify,
  type StrategyConfig,
} from '@/api/settings'

const authStore = useAuthStore()
const username = computed(() => authStore.username || '--')

const activeTab = ref('strategy')

// Strategy
const strategyLoaded = ref(false)
const saving = ref(false)
const strategy = reactive<StrategyConfig>({
  filter: {},
  score: {},
  position: {},
  risk: {},
})

const filterLabels: Record<string, string> = {
  min_market_cap: '最小市值（亿）',
  min_volume_ratio: '最小量比',
  max_pe: '最大市盈率',
  min_price: '最低价格',
  max_price: '最高价格',
  exclude_st: '排除ST',
}

const scoreLabels: Record<string, string> = {
  tech_weight: '技术权重',
  fund_weight: '资金权重',
  momentum_weight: '动量权重',
  sentiment_weight: '情绪权重',
  min_score: '最低评分',
}

const positionLabels: Record<string, string> = {
  max_positions: '最大持仓数',
  max_single_pct: '单只占比上限',
  max_sector_pct: '板块占比上限',
}

const riskLabels: Record<string, string> = {
  stop_loss_pct: '止损比例',
  take_profit_pct: '止盈比例',
  trailing_stop_pct: '追踪止损',
  max_drawdown_pct: '最大回撤',
}

async function loadStrategy() {
  try {
    const { data } = await getStrategy()
    Object.assign(strategy.filter, data.filter)
    Object.assign(strategy.score, data.score)
    Object.assign(strategy.position, data.position)
    Object.assign(strategy.risk, data.risk)
    strategyLoaded.value = true
  } catch {
    strategyLoaded.value = true
  }
}

async function saveStrategy() {
  saving.value = true
  try {
    await updateStrategy({
      filter: { ...strategy.filter },
      score: { ...strategy.score },
      position: { ...strategy.position },
      risk: { ...strategy.risk },
    })
    ElMessage.success('设置已保存')
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

// Notification
const notifyUrl = ref('')
const testMsg = ref('')
const testing = ref(false)

async function loadNotify() {
  try {
    const { data } = await getNotify()
    notifyUrl.value = data.feishu_webhook_url
  } catch {
    // API unavailable
  }
}

async function handleTest() {
  if (!testMsg.value) {
    ElMessage.warning('请输入测试消息')
    return
  }
  testing.value = true
  try {
    const { data } = await testNotify(testMsg.value)
    if (data.success) {
      ElMessage.success('测试消息已发送')
    } else {
      ElMessage.error('发送失败')
    }
  } catch {
    ElMessage.error('发送失败')
  } finally {
    testing.value = false
  }
}

onMounted(() => {
  loadStrategy()
  loadNotify()
})
</script>

<style scoped>
.settings-page {
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

/* -- Form -- */
.settings-form {
  width: 100%;
  max-width: 720px;
}

.param-group {
  margin-bottom: 28px;
}

.group-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--color-text);
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--color-border);
}

:deep(.el-form-item__label) {
  color: var(--color-text-secondary) !important;
  font-size: 13px;
}

:deep(.el-input__wrapper),
:deep(.el-textarea__inner) {
  background: var(--color-bg) !important;
  border: 1px solid var(--color-border) !important;
  box-shadow: none !important;
  color: var(--color-text) !important;
}

:deep(.el-input__inner) {
  color: var(--color-text) !important;
}

:deep(.el-input-number) {
  --el-input-number-bg-color: var(--color-bg);
}

:deep(.el-input-number .el-input-number__decrease),
:deep(.el-input-number .el-input-number__increase) {
  background: var(--color-surface-hover) !important;
  border-color: var(--color-border) !important;
  color: var(--color-text-secondary) !important;
}

.form-actions {
  padding-top: 16px;
  border-top: 1px solid var(--color-border);
}

:deep(.el-button--primary) {
  background: var(--color-accent);
  border-color: var(--color-accent);
  color: #0f0f23;
}

:deep(.el-button--primary:hover) {
  background: #5de0d7;
  border-color: #5de0d7;
}

/* -- Notify -- */
.test-row {
  display: flex;
  gap: 8px;
  width: 100%;
}

/* -- Account -- */
.account-val {
  font-size: 14px;
  color: var(--color-text);
  font-weight: 600;
}

.account-note {
  margin-top: 16px;
  padding: 12px 16px;
  background: var(--color-bg);
  border-radius: 8px;
  font-size: 13px;
  color: var(--color-text-secondary);
  border: 1px solid var(--color-border);
}

.empty-hint {
  text-align: center;
  color: var(--color-text-secondary);
  padding: 48px 0;
  font-size: 14px;
}
</style>
