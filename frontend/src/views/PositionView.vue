<template>
  <div class="position-page">
    <!-- Stats row -->
    <div class="stats-row">
      <div class="card card-stat" v-for="st in statCards" :key="st.label">
        <div class="stat-label">{{ st.label }}</div>
        <div class="stat-value" :class="st.cls">{{ st.value }}</div>
      </div>
    </div>

    <!-- Active positions -->
    <div class="section-header">
      <h2 class="section-title">活跃持仓</h2>
      <el-button type="primary" size="small" @click="showBuyDialog = true">
        记录买入
      </el-button>
    </div>

    <div class="pos-grid" v-if="activePositions.length > 0">
      <div v-for="pos in activePositions" :key="pos.id" class="card card-pos">
        <div class="pos-top">
          <div>
            <div class="pos-name">{{ pos.stock_name }}</div>
            <div class="pos-code">{{ pos.code }}</div>
          </div>
          <div class="pos-pnl" :class="pos.pnl_pct >= 0 ? 'up' : 'down'">
            {{ pos.pnl_pct >= 0 ? '+' : '' }}{{ pos.pnl_pct.toFixed(2) }}%
          </div>
        </div>

        <div class="pos-info-grid">
          <div class="pos-info">
            <span class="pos-info-label">买入价</span>
            <span class="pos-info-val">{{ pos.buy_price.toFixed(2) }}</span>
          </div>
          <div class="pos-info">
            <span class="pos-info-label">现价</span>
            <span class="pos-info-val">{{ pos.current_price.toFixed(2) }}</span>
          </div>
          <div class="pos-info">
            <span class="pos-info-label">持有天数</span>
            <span class="pos-info-val">{{ pos.hold_days }}天</span>
          </div>
          <div class="pos-info">
            <span class="pos-info-label">持仓数量</span>
            <span class="pos-info-val">{{ pos.shares }}股</span>
          </div>
        </div>

        <!-- Risk progress bar -->
        <div class="risk-bar-wrapper">
          <div class="risk-labels">
            <span class="risk-stop">止损 {{ pos.stop_loss_price.toFixed(2) }}</span>
            <span class="risk-target">目标 {{ pos.take_profit_price.toFixed(2) }}</span>
          </div>
          <div class="risk-bar">
            <div class="risk-fill" :style="riskStyle(pos)" />
            <div class="risk-marker" :style="riskMarkerStyle(pos)" />
          </div>
        </div>

        <div class="pos-actions">
          <el-button
            size="small"
            type="danger"
            plain
            @click="openClose(pos)"
          >
            平仓
          </el-button>
        </div>
      </div>
    </div>
    <div v-else class="empty-hint">暂无活跃持仓</div>

    <!-- Trade history -->
    <div class="section-header" style="margin-top: 32px;">
      <h2 class="section-title">交易记录</h2>
    </div>
    <div class="card card-trades">
      <el-table :data="trades" class="dark-table" v-if="trades.length > 0">
        <el-table-column prop="trade_date" label="日期" width="110" />
        <el-table-column prop="stock_name" label="名称" width="100" />
        <el-table-column prop="code" label="代码" width="90">
          <template #default="{ row }">
            <span class="mono">{{ row.code }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="action" label="操作" width="70" align="center">
          <template #default="{ row }">
            <span class="trade-action" :class="row.action">
              {{ row.action === 'buy' ? '买入' : '卖出' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="price" label="价格" width="90" align="right">
          <template #default="{ row }">
            <span class="mono">{{ row.price?.toFixed(2) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="shares" label="数量" width="80" align="right" />
        <el-table-column prop="amount" label="金额" width="110" align="right">
          <template #default="{ row }">
            <span class="mono">{{ row.amount?.toFixed(2) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="reason" label="原因" min-width="200" show-overflow-tooltip />
      </el-table>
      <div v-else class="empty-hint">暂无交易记录</div>
    </div>

    <!-- Buy dialog -->
    <el-dialog
      v-model="showBuyDialog"
      title="记录买入"
      width="420px"
      class="dark-dialog"
      :close-on-click-modal="false"
    >
      <el-form :model="buyForm" label-width="80px" label-position="left">
        <el-form-item label="股票代码">
          <el-input v-model="buyForm.code" placeholder="如 000001" />
        </el-form-item>
        <el-form-item label="股票名称">
          <el-input v-model="buyForm.stock_name" placeholder="如 平安银行" />
        </el-form-item>
        <el-form-item label="买入价格">
          <el-input-number v-model="buyForm.buy_price" :precision="2" :min="0" controls-position="right" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="买入数量">
          <el-input-number v-model="buyForm.shares" :min="100" :step="100" controls-position="right" style="width: 100%;" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showBuyDialog = false">取消</el-button>
        <el-button type="primary" :loading="buyLoading" @click="handleBuy">确认买入</el-button>
      </template>
    </el-dialog>

    <!-- Close dialog -->
    <el-dialog
      v-model="showCloseDialog"
      title="平仓"
      width="420px"
      class="dark-dialog"
      :close-on-click-modal="false"
    >
      <div class="close-info" v-if="closingPos">
        <span>{{ closingPos.stock_name }}（{{ closingPos.code }}）</span>
        <span class="close-shares">{{ closingPos.shares }}股</span>
      </div>
      <el-form :model="closeForm" label-width="80px" label-position="left" style="margin-top: 16px;">
        <el-form-item label="平仓价格">
          <el-input-number v-model="closeForm.close_price" :precision="2" :min="0" controls-position="right" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="平仓原因">
          <el-input v-model="closeForm.close_reason" type="textarea" :rows="2" placeholder="如 止盈 / 止损 / 手动" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCloseDialog = false">取消</el-button>
        <el-button type="danger" :loading="closeLoading" @click="handleClose">确认平仓</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  fetchPositions,
  createPosition,
  closePosition,
  fetchTrades,
  fetchStats,
  type PositionItem,
  type TradeRecord,
  type PositionStats,
} from '@/api/position'

const positions = ref<PositionItem[]>([])
const trades = ref<TradeRecord[]>([])
const stats = ref<Partial<PositionStats>>({})

const activePositions = computed(() => positions.value.filter((p) => p.status === 'open'))

const statCards = computed(() => [
  { label: '总交易', value: String(stats.value.total_trades ?? 0), cls: '' },
  {
    label: '胜率',
    value: ((stats.value.win_rate ?? 0) * 100).toFixed(1) + '%',
    cls: (stats.value.win_rate ?? 0) >= 0.5 ? 'up' : 'down',
  },
  {
    label: '总收益',
    value: (stats.value.total_pnl ?? 0) >= 0
      ? '+' + (stats.value.total_pnl ?? 0).toFixed(2) + '%'
      : (stats.value.total_pnl ?? 0).toFixed(2) + '%',
    cls: (stats.value.total_pnl ?? 0) >= 0 ? 'up' : 'down',
  },
  { label: '平均持有', value: (stats.value.avg_hold_days ?? 0).toFixed(0) + '天', cls: '' },
])

// Risk bar helpers
function riskStyle(pos: PositionItem) {
  const range = pos.take_profit_price - pos.stop_loss_price
  if (range <= 0) return { width: '0%' }
  const progress = Math.max(0, Math.min(1, (pos.current_price - pos.stop_loss_price) / range))
  return { width: (progress * 100) + '%' }
}

function riskMarkerStyle(pos: PositionItem) {
  const range = pos.take_profit_price - pos.stop_loss_price
  if (range <= 0) return { left: '0%' }
  const buyPos = Math.max(0, Math.min(1, (pos.buy_price - pos.stop_loss_price) / range))
  return { left: (buyPos * 100) + '%' }
}

// Buy dialog
const showBuyDialog = ref(false)
const buyLoading = ref(false)
const buyForm = reactive({
  code: '',
  stock_name: '',
  buy_price: 0,
  shares: 100,
})

async function handleBuy() {
  if (!buyForm.code || !buyForm.stock_name || buyForm.buy_price <= 0) {
    ElMessage.warning('请填写完整信息')
    return
  }
  buyLoading.value = true
  try {
    await createPosition({
      code: buyForm.code,
      stock_name: buyForm.stock_name,
      buy_price: buyForm.buy_price,
      shares: buyForm.shares,
    })
    ElMessage.success('买入记录已创建')
    showBuyDialog.value = false
    buyForm.code = ''
    buyForm.stock_name = ''
    buyForm.buy_price = 0
    buyForm.shares = 100
    await loadData()
  } catch {
    ElMessage.error('操作失败')
  } finally {
    buyLoading.value = false
  }
}

// Close dialog
const showCloseDialog = ref(false)
const closeLoading = ref(false)
const closingPos = ref<PositionItem | null>(null)
const closeForm = reactive({
  close_price: 0,
  close_reason: '',
})

function openClose(pos: PositionItem) {
  closingPos.value = pos
  closeForm.close_price = pos.current_price
  closeForm.close_reason = ''
  showCloseDialog.value = true
}

async function handleClose() {
  if (!closingPos.value || closeForm.close_price <= 0) return
  closeLoading.value = true
  try {
    await closePosition(closingPos.value.id, {
      close_price: closeForm.close_price,
      close_reason: closeForm.close_reason,
    })
    ElMessage.success('平仓成功')
    showCloseDialog.value = false
    await loadData()
  } catch {
    ElMessage.error('操作失败')
  } finally {
    closeLoading.value = false
  }
}

async function loadData() {
  try {
    const [posRes, tradeRes, statsRes] = await Promise.all([
      fetchPositions(),
      fetchTrades(50),
      fetchStats(),
    ])
    positions.value = posRes.data
    trades.value = tradeRes.data
    Object.assign(stats, { value: statsRes.data })
    stats.value = statsRes.data
  } catch {
    // API unavailable
  }
}

onMounted(loadData)
</script>

<style scoped>
.position-page {
  max-width: 1400px;
}

.card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  padding: 20px;
}

.mono { font-variant-numeric: tabular-nums; }
.up { color: var(--color-danger); }
.down { color: var(--color-success); }

/* -- Stats row -- */
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 28px;
}

.card-stat {
  text-align: center;
}

.stat-label {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-bottom: 8px;
}

.stat-value {
  font-size: 24px;
  font-weight: 800;
  color: var(--color-text);
  font-variant-numeric: tabular-nums;
}

/* -- Section header -- */
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.section-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--color-text);
}

/* -- Position cards -- */
.pos-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}

.card-pos {
  transition: border-color 0.2s;
}

.card-pos:hover {
  border-color: var(--color-accent);
}

.pos-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 14px;
}

.pos-name {
  font-size: 16px;
  font-weight: 700;
  color: var(--color-text);
}

.pos-code {
  font-size: 12px;
  color: var(--color-text-secondary);
  font-variant-numeric: tabular-nums;
}

.pos-pnl {
  font-size: 22px;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}

.pos-info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px 16px;
  margin-bottom: 14px;
}

.pos-info {
  display: flex;
  justify-content: space-between;
}

.pos-info-label {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.pos-info-val {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text);
  font-variant-numeric: tabular-nums;
}

/* -- Risk bar -- */
.risk-bar-wrapper {
  margin-bottom: 14px;
}

.risk-labels {
  display: flex;
  justify-content: space-between;
  margin-bottom: 4px;
}

.risk-stop {
  font-size: 11px;
  color: var(--color-success);
}

.risk-target {
  font-size: 11px;
  color: var(--color-danger);
}

.risk-bar {
  height: 6px;
  background: rgba(42, 42, 74, 0.6);
  border-radius: 3px;
  position: relative;
  overflow: visible;
}

.risk-fill {
  height: 100%;
  border-radius: 3px;
  background: linear-gradient(90deg, var(--color-success), var(--color-warning), var(--color-danger));
  transition: width 0.5s ease;
}

.risk-marker {
  position: absolute;
  top: -3px;
  width: 4px;
  height: 12px;
  background: var(--color-text);
  border-radius: 2px;
  transform: translateX(-2px);
}

.pos-actions {
  display: flex;
  justify-content: flex-end;
}

/* -- Trades table -- */
.card-trades {
  margin-bottom: 20px;
}

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

.trade-action {
  font-size: 12px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 4px;
}

.trade-action.buy {
  background: rgba(239, 83, 80, 0.12);
  color: var(--color-danger);
}

.trade-action.sell {
  background: rgba(38, 166, 154, 0.12);
  color: var(--color-success);
}

.empty-hint {
  text-align: center;
  color: var(--color-text-secondary);
  padding: 40px 0;
  font-size: 14px;
}

/* -- Dialog overrides -- */
:deep(.el-dialog) {
  background: var(--color-surface) !important;
  border: 1px solid var(--color-border);
  border-radius: 14px;
}

:deep(.el-dialog__title) {
  color: var(--color-text) !important;
  font-weight: 700;
}

:deep(.el-dialog__headerbtn .el-dialog__close) {
  color: var(--color-text-secondary);
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

:deep(.el-form-item__label) {
  color: var(--color-text-secondary) !important;
}

.close-info {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: var(--color-bg);
  border-radius: 8px;
  font-size: 14px;
  color: var(--color-text);
}

.close-shares {
  color: var(--color-text-secondary);
  font-size: 13px;
}

/* -- Button overrides -- */
:deep(.el-button--primary) {
  background: var(--color-accent);
  border-color: var(--color-accent);
  color: #0f0f23;
}

:deep(.el-button--primary:hover) {
  background: #5de0d7;
  border-color: #5de0d7;
}
</style>
