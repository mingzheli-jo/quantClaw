<template>
  <div class="ai-insight">
    <div class="page-header">
      <h2>AI 洞察</h2>
      <span class="sub">{{ items.length }} 条分析</span>
    </div>

    <div v-if="items.length === 0" class="empty-state">
      <p>暂无 AI 分析数据</p>
      <p class="hint">系统会在每个交易日 15:40 自动生成 TOP 信号、持仓和自选股的分析</p>
    </div>

    <div class="analysis-list">
      <div v-for="item in items" :key="item.code" class="analysis-card" @click="goDetail(item.code)">
        <div class="card-header">
          <div class="stock-info">
            <span class="stock-name">{{ item.stock_name }}</span>
            <span class="stock-code">{{ item.code }}</span>
          </div>
          <span class="score-tag">{{ item.score }}分</span>
        </div>
        <div class="card-body">
          <div class="section" v-if="item.summary">
            <div class="section-label">推荐理由</div>
            <p>{{ item.summary }}</p>
          </div>
          <div class="section" v-if="item.risk">
            <div class="section-label">风险提示</div>
            <p>{{ item.risk }}</p>
          </div>
          <div class="section" v-if="item.suggestion">
            <div class="section-label">操作建议</div>
            <p>{{ item.suggestion }}</p>
          </div>
          <div class="section" v-if="item.market_comment">
            <div class="section-label">市场环境</div>
            <p>{{ item.market_comment }}</p>
          </div>
        </div>
        <div class="card-footer">
          <span class="provider">{{ item.llm_provider }}</span>
          <span class="time">{{ item.created_at?.slice(11, 16) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { fetchDailyAnalyses, type AIAnalysisItem } from '@/api/ai'

const router = useRouter()
const items = ref<AIAnalysisItem[]>([])

function goDetail(code: string) {
  router.push(`/stock/${code}`)
}

onMounted(async () => {
  try {
    const { data } = await fetchDailyAnalyses()
    items.value = data
  } catch {}
})
</script>

<style scoped>
.page-header { display: flex; align-items: baseline; gap: 12px; margin-bottom: 24px; }
.page-header h2 { font-size: 20px; font-weight: 700; color: var(--color-text); }
.sub { font-size: 14px; color: var(--color-text-secondary); }

.empty-state { text-align: center; padding: 60px 0; color: var(--color-text-secondary); }
.hint { font-size: 13px; margin-top: 8px; }

.analysis-list { display: flex; flex-direction: column; gap: 16px; }

.analysis-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  padding: 20px;
  cursor: pointer;
  transition: border-color 0.2s;
}
.analysis-card:hover { border-color: var(--color-accent); }

.card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.stock-info { display: flex; align-items: baseline; gap: 8px; }
.stock-name { font-size: 16px; font-weight: 700; color: var(--color-text); }
.stock-code { font-size: 13px; color: var(--color-accent); font-variant-numeric: tabular-nums; }
.score-tag {
  font-size: 13px; font-weight: 600; color: var(--color-accent);
  background: rgba(78, 205, 196, 0.1); padding: 4px 10px; border-radius: 6px;
}

.section { margin-bottom: 12px; }
.section-label { font-size: 13px; font-weight: 600; color: var(--color-text-secondary); margin-bottom: 4px; }
.section p { font-size: 14px; color: var(--color-text); line-height: 1.6; margin: 0; }

.card-footer { display: flex; justify-content: space-between; font-size: 12px; color: var(--color-text-secondary); margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--color-border); }
</style>
