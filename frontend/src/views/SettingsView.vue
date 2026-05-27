<template>
  <div class="settings-page">
    <el-tabs v-model="activeTab" class="dark-tabs">
      <!-- Strategy Tab -->
      <el-tab-pane label="策略参数" name="strategy">
        <!-- Data Source Card -->
        <div class="card" style="margin-bottom: 16px;">
          <h3 class="group-title">数据源</h3>
          <el-form label-width="140px" label-position="left" class="settings-form">
            <el-form-item label="数据来源">
              <select
                v-model="dataSource"
                @change="onDataSourceChange"
                class="datasource-select"
              >
                <option
                  v-for="src in availableSources"
                  :key="src"
                  :value="src"
                >{{ sourceLabels[src] || src }}</option>
              </select>
            </el-form-item>
            <el-form-item v-if="dataSource === 'baostock'" label=" ">
              <span class="datasource-hint">BaoStock 不支持北向资金和板块数据，这些模块将显示为空。</span>
            </el-form-item>
          </el-form>
        </div>

        <!-- Strategy Management Card -->
        <div class="card settings-card" style="margin-bottom: 16px;">
          <h3 class="settings-title">策略管理</h3>
          <div class="strategy-grid">
            <div v-for="s in strategies" :key="s.id" class="strategy-card" :class="{ active: s.is_active }">
              <div class="strat-header">
                <span class="strat-name">{{ s.name }}</span>
                <span v-if="s.is_active" class="strat-badge">当前激活</span>
                <span v-if="s.is_builtin" class="strat-builtin">内置</span>
              </div>
              <p class="strat-desc">{{ s.description }}</p>
              <div class="strat-weights">
                <span class="weight-tag">技{{ Math.round(s.score_config.tech_weight * 100) }}</span>
                <span class="weight-tag">资{{ Math.round(s.score_config.fund_weight * 100) }}</span>
                <span class="weight-tag">动{{ Math.round(s.score_config.momentum_weight * 100) }}</span>
                <span class="weight-tag">情{{ Math.round(s.score_config.sentiment_weight * 100) }}</span>
              </div>
              <div class="strat-actions">
                <button v-if="!s.is_active" class="strat-btn" @click="onActivate(s.id)">激活</button>
                <button class="strat-btn" @click="onDuplicate(s)">复制</button>
                <button v-if="!s.is_builtin" class="strat-btn strat-btn-danger" @click="onDeleteStrategy(s.id)">删除</button>
              </div>
            </div>
          </div>
        </div>

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

      <!-- AI Config Tab -->
      <el-tab-pane label="AI 配置" name="ai">
        <div class="card">
          <h3 class="group-title">AI 分析模型</h3>
          <el-form label-width="140px" label-position="left" class="settings-form">
            <el-form-item label="当前模型">
              <el-radio-group v-model="aiProvider" @change="onAIProviderChange">
                <el-radio-button value="deepseek">
                  DeepSeek
                  <el-tag v-if="aiConfig?.deepseek_configured" type="success" size="small" style="margin-left: 6px">已配置</el-tag>
                  <el-tag v-else type="info" size="small" style="margin-left: 6px">未配置</el-tag>
                </el-radio-button>
                <el-radio-button value="qwen">
                  通义千问
                  <el-tag v-if="aiConfig?.qwen_configured" type="success" size="small" style="margin-left: 6px">已配置</el-tag>
                  <el-tag v-else type="info" size="small" style="margin-left: 6px">未配置</el-tag>
                </el-radio-button>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="DeepSeek API Key">
              <div class="key-row">
                <el-input
                  v-model="deepseekKey"
                  type="password"
                  show-password
                  placeholder="sk-..."
                  style="flex: 1"
                />
                <el-button @click="saveAIKey('deepseek')" :loading="aiSaving">保存</el-button>
              </div>
            </el-form-item>
            <el-form-item label="通义千问 API Key">
              <div class="key-row">
                <el-input
                  v-model="qwenKey"
                  type="password"
                  show-password
                  placeholder="sk-..."
                  style="flex: 1"
                />
                <el-button @click="saveAIKey('qwen')" :loading="aiSaving">保存</el-button>
              </div>
            </el-form-item>
          </el-form>
          <div class="ai-hint">
            <p>DeepSeek: 注册 <a href="https://platform.deepseek.com" target="_blank">platform.deepseek.com</a> 获取 API Key，每月约 1-5 元</p>
            <p>通义千问: 注册 <a href="https://dashscope.aliyun.com" target="_blank">dashscope.aliyun.com</a> 获取 API Key</p>
          </div>
        </div>
      </el-tab-pane>

      <!-- Schedule Tab -->
      <el-tab-pane label="定时任务" name="schedules">
        <div class="card">
          <h3 class="group-title">任务调度配置</h3>
          <p class="schedule-hint">修改后立即生效，无需重启服务</p>
          <el-table :data="schedules" stripe style="margin-top: 16px">
            <el-table-column prop="label" label="任务" width="140" />
            <el-table-column label="执行时间" width="250">
              <template #default="{ row }">
                <div v-if="row.schedule_type === 'cron'" class="time-inputs">
                  <el-input-number
                    v-model="row.hour"
                    :min="0" :max="23"
                    controls-position="right"
                    size="small"
                    style="width: 90px"
                    @change="onScheduleChange(row)"
                  />
                  <span class="time-sep">:</span>
                  <el-input-number
                    v-model="row.minute"
                    :min="0" :max="59"
                    controls-position="right"
                    size="small"
                    style="width: 90px"
                    @change="onScheduleChange(row)"
                  />
                </div>
                <div v-else class="time-inputs">
                  <el-input-number
                    v-model="row.interval_seconds"
                    :min="10" :max="3600"
                    :step="10"
                    controls-position="right"
                    size="small"
                    style="width: 140px"
                    @change="onScheduleChange(row)"
                  />
                  <span class="time-unit">秒</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-switch
                  v-model="row.enabled"
                  @change="onScheduleChange(row)"
                />
              </template>
            </el-table-column>
            <el-table-column label="类型" width="100">
              <template #default="{ row }">
                <el-tag size="small" :type="row.schedule_type === 'cron' ? '' : 'success'">
                  {{ row.schedule_type === 'cron' ? '定时' : '循环' }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
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
  getDataSource,
  setDataSource,
  fetchSchedules,
  updateSchedule,
  fetchAIConfig,
  updateAIConfig,
  type StrategyConfig,
  type JobScheduleItem,
  type AIConfig,
} from '@/api/settings'
import {
  listStrategies,
  activateStrategy,
  createStrategy,
  deleteStrategy,
  type StrategyTemplate,
} from '@/api/strategy'

const authStore = useAuthStore()
const username = computed(() => authStore.username || '--')

const activeTab = ref('strategy')

// Strategy
const strategyLoaded = ref(false)
const saving = ref(false)
const strategies = ref<StrategyTemplate[]>([])
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

async function loadStrategies() {
  try {
    const { data } = await listStrategies()
    strategies.value = data
  } catch {}
}

async function onActivate(id: number) {
  await activateStrategy(id)
  await loadStrategies()
}

async function onDuplicate(strategy: StrategyTemplate) {
  await createStrategy({
    name: strategy.name + ' (副本)',
    description: strategy.description,
    filter_config: strategy.filter_config,
    score_config: strategy.score_config,
    signal_config: strategy.signal_config,
    risk_config: strategy.risk_config,
  })
  await loadStrategies()
}

async function onDeleteStrategy(id: number) {
  await deleteStrategy(id)
  await loadStrategies()
}

// Data Source
const dataSource = ref('eastmoney')
const availableSources = ref<string[]>([])
const sourceLabels: Record<string, string> = {
  eastmoney: '东方财富 (推荐)',
  baostock: 'BaoStock',
}

async function loadDataSource() {
  try {
    const { data } = await getDataSource()
    dataSource.value = data.source
    availableSources.value = data.available
  } catch {}
}

async function onDataSourceChange() {
  try {
    await setDataSource(dataSource.value)
  } catch {}
}

// Schedules
const schedules = ref<JobScheduleItem[]>([])

async function loadSchedules() {
  try {
    const { data } = await fetchSchedules()
    schedules.value = data
  } catch {}
}

async function onScheduleChange(row: JobScheduleItem) {
  try {
    await updateSchedule(row.job_id, {
      hour: row.hour,
      minute: row.minute,
      interval_seconds: row.interval_seconds,
      enabled: row.enabled,
    })
  } catch {}
}

// AI Config
const aiConfig = ref<AIConfig | null>(null)
const aiProvider = ref('deepseek')
const deepseekKey = ref('')
const qwenKey = ref('')
const aiSaving = ref(false)

async function loadAIConfig() {
  try {
    const { data } = await fetchAIConfig()
    aiConfig.value = data
    aiProvider.value = data.provider
  } catch {}
}

async function onAIProviderChange(val: string) {
  try {
    const { data } = await updateAIConfig({ provider: val })
    aiConfig.value = data
    ElMessage.success('AI 模型已切换为 ' + (val === 'deepseek' ? 'DeepSeek' : '通义千问'))
  } catch {}
}

async function saveAIKey(provider: string) {
  aiSaving.value = true
  try {
    const payload: Record<string, string> = {}
    if (provider === 'deepseek') payload.deepseek_api_key = deepseekKey.value
    if (provider === 'qwen') payload.qwen_api_key = qwenKey.value
    const { data } = await updateAIConfig(payload)
    aiConfig.value = data
    ElMessage.success('API Key 已保存')
    if (provider === 'deepseek') deepseekKey.value = ''
    if (provider === 'qwen') qwenKey.value = ''
  } catch {}
  aiSaving.value = false
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
  loadDataSource()
  loadStrategies()
  loadSchedules()
  loadAIConfig()
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

/* -- Data Source -- */
.datasource-select {
  appearance: none;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  color: var(--color-text);
  font-size: 13px;
  padding: 6px 32px 6px 12px;
  width: 240px;
  cursor: pointer;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8'%3E%3Cpath d='M1 1l5 5 5-5' stroke='%2366e0d6' stroke-width='1.5' fill='none' stroke-linecap='round'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 10px center;
}

.datasource-select:focus {
  outline: none;
  border-color: var(--color-accent);
}

.datasource-hint {
  font-size: 12px;
  color: var(--color-text-secondary);
  line-height: 1.6;
}

/* -- Strategy Management -- */
.settings-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--color-text);
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--color-border);
}

.strategy-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 14px;
}

.strategy-card {
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 10px;
  padding: 14px 16px;
}

.strategy-card.active {
  border-color: rgba(59,130,246,0.4);
  background: rgba(59,130,246,0.05);
}

.strat-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.strat-name {
  font-weight: 600;
  font-size: 15px;
}

.strat-badge {
  background: #3b82f6;
  color: #fff;
  font-size: 11px;
  padding: 1px 8px;
  border-radius: 4px;
}

.strat-builtin {
  font-size: 11px;
  color: #8b95a5;
  border: 1px solid rgba(255,255,255,0.1);
  padding: 1px 6px;
  border-radius: 4px;
}

.strat-desc {
  font-size: 12px;
  color: #8b95a5;
  margin: 0 0 8px 0;
  line-height: 1.4;
}

.strat-weights {
  display: flex;
  gap: 6px;
  margin-bottom: 10px;
}

.weight-tag {
  background: rgba(255,255,255,0.06);
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 4px;
  color: #ccc;
}

.strat-actions {
  display: flex;
  gap: 8px;
}

.strat-btn {
  background: rgba(255,255,255,0.08);
  border: none;
  border-radius: 5px;
  padding: 5px 12px;
  color: #e0e6ed;
  font-size: 12px;
  cursor: pointer;
}

.strat-btn:hover {
  background: rgba(255,255,255,0.14);
}

.strat-btn-danger {
  color: #ef4444;
}

.schedule-hint { font-size: 13px; color: var(--color-text-secondary); margin-top: 8px; }
.time-inputs { display: flex; align-items: center; gap: 4px; }
.time-sep { font-size: 16px; font-weight: 700; color: var(--color-text); }
.time-unit { font-size: 13px; color: var(--color-text-secondary); margin-left: 4px; }

.key-row { display: flex; gap: 8px; width: 100%; }
.ai-hint { margin-top: 16px; padding: 12px; background: rgba(78, 205, 196, 0.05); border-radius: 8px; }
.ai-hint p { font-size: 13px; color: var(--color-text-secondary); margin: 4px 0; }
.ai-hint a { color: var(--color-accent); text-decoration: none; }
</style>
